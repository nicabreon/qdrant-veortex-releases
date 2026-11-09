#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef int (*pthread_setname_fn)(pthread_t, const char *);

static pthread_setname_fn next_pthread_setname_np;
static int bench_compute_cpu = -1;
static int bench_affinity_enabled;
static cpu_set_t bench_support_cpus;

static void set_affinity_and_verify(const cpu_set_t *desired,
                                    const char *failure_context);

static _Noreturn void fail_fast(const char *context, int error_number) {
    char message[512];
    int length;

    if (error_number != 0) {
        length = snprintf(message, sizeof(message),
                          "qdrant-search-affinity: FATAL: %s: %s (errno=%d)\n",
                          context, strerror(error_number), error_number);
    } else {
        length = snprintf(message, sizeof(message),
                          "qdrant-search-affinity: FATAL: %s\n", context);
    }
    if (length > 0) {
        size_t to_write = (size_t) length;
        if (to_write >= sizeof(message)) {
            to_write = sizeof(message) - 1;
        }
        ssize_t written = write(STDERR_FILENO, message, to_write);
        if (written < 0) {
            _exit(126);
        }
    }
    _exit(126);
}

static int parse_cpu_id(const char *value) {
    unsigned long result = 0;

    if (value == NULL || *value == '\0') {
        fail_fast("BENCH_COMPUTE_CPU must be a decimal CPU number", 0);
    }
    for (const unsigned char *cursor = (const unsigned char *) value;
         *cursor != '\0'; ++cursor) {
        if (*cursor < '0' || *cursor > '9') {
            fail_fast("BENCH_COMPUTE_CPU must contain only decimal digits", 0);
        }
        result = result * 10UL + (unsigned long) (*cursor - '0');
        if (result >= (unsigned long) CPU_SETSIZE) {
            fail_fast("BENCH_COMPUTE_CPU exceeds CPU_SETSIZE", 0);
        }
    }
    return (int) result;
}

static unsigned long parse_decimal_component(const char **cursor) {
    unsigned long result = 0;
    const char *start = *cursor;

    if (**cursor < '0' || **cursor > '9') {
        fail_fast("BENCH_SUPPORT_CPUS must be an integer cpuset", 0);
    }
    while (**cursor >= '0' && **cursor <= '9') {
        result = result * 10UL + (unsigned long) (**cursor - '0');
        if (result >= (unsigned long) CPU_SETSIZE) {
            fail_fast("BENCH_SUPPORT_CPUS contains an out-of-range CPU", 0);
        }
        ++(*cursor);
    }
    if (*cursor == start) {
        fail_fast("BENCH_SUPPORT_CPUS must be an integer cpuset", 0);
    }
    return result;
}

static void parse_support_cpuset(const char *value, cpu_set_t *set) {
    unsigned int count = 0;
    const char *cursor = value;

    if (value == NULL || *value == '\0') {
        fail_fast("BENCH_SUPPORT_CPUS must contain two CPU ids", 0);
    }
    CPU_ZERO(set);
    while (*cursor != '\0') {
        unsigned long first = parse_decimal_component(&cursor);
        unsigned long last = first;
        if (*cursor == '-') {
            ++cursor;
            last = parse_decimal_component(&cursor);
            if (last < first) {
                fail_fast("BENCH_SUPPORT_CPUS range end precedes its start", 0);
            }
        }
        for (unsigned long cpu = first; cpu <= last; ++cpu) {
            if (CPU_ISSET((int) cpu, set)) {
                fail_fast("BENCH_SUPPORT_CPUS contains duplicate CPU ids", 0);
            }
            CPU_SET((int) cpu, set);
            ++count;
        }
        if (*cursor == '\0') {
            break;
        }
        if (*cursor != ',') {
            fail_fast("BENCH_SUPPORT_CPUS must be a comma-separated integer cpuset",
                      0);
        }
        ++cursor;
        if (*cursor == '\0') {
            fail_fast("BENCH_SUPPORT_CPUS must not end with a comma", 0);
        }
    }
    if (count != 2U) {
        fail_fast("BENCH_SUPPORT_CPUS must name exactly two support CPUs", 0);
    }
}

static int is_qdrant_search_thread(const char *name) {
    if (name == NULL) {
        return 0;
    }
    return strncmp(name, "search-cpu-", sizeof("search-cpu-") - 1) == 0 ||
           strncmp(name, "search-io-", sizeof("search-io-") - 1) == 0 ||
           strncmp(name, "search-ioall-", sizeof("search-ioall-") - 1) == 0;
}

static void set_current_thread_affinity(void) {
    cpu_set_t desired;

    CPU_ZERO(&desired);
    CPU_SET(bench_compute_cpu, &desired);
    set_affinity_and_verify(&desired,
                            "sched_setaffinity failed for a named Qdrant search worker");
}

static void set_affinity_and_verify(const cpu_set_t *desired,
                                    const char *failure_context) {
    cpu_set_t actual;

    if (sched_setaffinity(0, sizeof(*desired), desired) != 0) {
        fail_fast(failure_context, errno);
    }
    CPU_ZERO(&actual);
    if (sched_getaffinity(0, sizeof(actual), &actual) != 0) {
        fail_fast("sched_getaffinity failed after setting a benchmark affinity",
                  errno);
    }
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        if (CPU_ISSET(cpu, desired) != CPU_ISSET(cpu, &actual)) {
            fail_fast("thread affinity differs from the requested benchmark cpuset",
                      0);
        }
    }
}

__attribute__((constructor)) static void initialize_search_affinity(void) {
    const char *compute_value = getenv("BENCH_COMPUTE_CPU");
    const char *support_value = getenv("BENCH_SUPPORT_CPUS");
    void *symbol;
    const char *loader_error;
    cpu_set_t allowed_union;

    /* Without either benchmark variable the preload is a transparent pass-through. */
    if (compute_value == NULL && support_value == NULL) {
        bench_affinity_enabled = 0;
    } else {
        if (compute_value == NULL || support_value == NULL) {
            fail_fast("BENCH_COMPUTE_CPU and BENCH_SUPPORT_CPUS must be set together",
                      0);
        }
        bench_compute_cpu = parse_cpu_id(compute_value);
        parse_support_cpuset(support_value, &bench_support_cpus);
        if (CPU_ISSET(bench_compute_cpu, &bench_support_cpus)) {
            fail_fast("BENCH_COMPUTE_CPU must be separate from BENCH_SUPPORT_CPUS",
                      0);
        }

        CPU_ZERO(&allowed_union);
        CPU_SET(bench_compute_cpu, &allowed_union);
        for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
            if (CPU_ISSET(cpu, &bench_support_cpus)) {
                CPU_SET(cpu, &allowed_union);
            }
        }

        /*
         * An exec'd shell/tool may start with only the two support CPUs in its
         * inherited thread mask. Ask the kernel for the full requested union;
         * its cpuset cgroup intersects this with the container's legal CPUs.
         * An incomplete result means the compute CPU is outside that cgroup.
         */
        set_affinity_and_verify(&allowed_union,
                                "requested benchmark CPUs are outside the container cpuset");
        bench_affinity_enabled = 1;
        set_affinity_and_verify(&bench_support_cpus,
                                "could not pin the Qdrant main thread to BENCH_SUPPORT_CPUS");
    }

    (void) dlerror();
    symbol = dlsym(RTLD_NEXT, "pthread_setname_np");
    loader_error = dlerror();
    if (loader_error != NULL || symbol == NULL) {
        fail_fast("could not resolve the real pthread_setname_np", 0);
    }
    if (sizeof(next_pthread_setname_np) != sizeof(symbol)) {
        fail_fast("function-pointer size differs from the dynamic-loader symbol size",
                  0);
    }
    memcpy(&next_pthread_setname_np, &symbol,
           sizeof(next_pthread_setname_np));
}

int pthread_setname_np(pthread_t thread, const char *name) {
    int matches = bench_affinity_enabled && is_qdrant_search_thread(name);
    int result;

    if (next_pthread_setname_np == NULL) {
        fail_fast("pthread_setname_np interposer was not initialized", 0);
    }
    if (matches && !pthread_equal(thread, pthread_self())) {
        fail_fast("Qdrant search worker was named from a different thread; refusing a late pin",
                  0);
    }

    result = next_pthread_setname_np(thread, name);
    if (matches) {
        if (result != 0) {
            fail_fast("pthread_setname_np failed for a Qdrant search worker", result);
        }
        /* The named Rust worker cannot leave pthread_setname_np until this pin succeeds. */
        set_current_thread_affinity();
    }
    return result;
}
