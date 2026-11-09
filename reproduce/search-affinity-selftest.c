#define _GNU_SOURCE

#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

struct worker_case {
    const char *name;
    int expected_cpu;
};

static atomic_int work_started;
static cpu_set_t expected_affinity;

static void *check_named_worker(void *opaque) {
    const struct worker_case *worker = opaque;
    cpu_set_t affinity;
    int result;

    result = pthread_setname_np(pthread_self(), worker->name);
    if (result != 0) {
        fprintf(stderr, "selftest: pthread_setname_np(%s): %s\n",
                worker->name, strerror(result));
        return (void *) 1;
    }

    CPU_ZERO(&affinity);
    if (sched_getaffinity(0, sizeof(affinity), &affinity) != 0) {
        fprintf(stderr, "selftest: sched_getaffinity(%s): %s\n",
                worker->name, strerror(errno));
        return (void *) 1;
    }
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        int expected = worker->expected_cpu >= 0
            ? cpu == worker->expected_cpu
            : CPU_ISSET(cpu, &expected_affinity);
        if (CPU_ISSET(cpu, &affinity) != expected) {
            fprintf(stderr,
                    "selftest: %s affinity mismatch before work (expected CPU %d)\n",
                    worker->name, worker->expected_cpu);
            return (void *) 1;
        }
    }

    /* First simulated work follows the name-and-affinity setup above. */
    atomic_fetch_add_explicit(&work_started, 1, memory_order_release);
    return NULL;
}

static int parse_cpu_id(const char *value) {
    char *end = NULL;
    long parsed;

    if (value == NULL || *value == '\0') {
        fprintf(stderr, "selftest: BENCH_COMPUTE_CPU is required\n");
        return -1;
    }
    errno = 0;
    parsed = strtol(value, &end, 10);
    if (errno != 0 || end == value || *end != '\0' || parsed < 0 ||
        parsed >= CPU_SETSIZE) {
        fprintf(stderr, "selftest: invalid BENCH_COMPUTE_CPU: %s\n", value);
        return -1;
    }
    return (int) parsed;
}

static int parse_cpu_list(const char *value, cpu_set_t *set) {
    char *copy;
    char *cursor;

    if (value == NULL || *value == '\0') {
        fprintf(stderr, "selftest: BENCH_EXPECTED_CPUSET is required in pass-through mode\n");
        return -1;
    }
    copy = strdup(value);
    if (copy == NULL) {
        fprintf(stderr, "selftest: could not copy BENCH_EXPECTED_CPUSET\n");
        return -1;
    }
    CPU_ZERO(set);
    cursor = copy;
    while (cursor != NULL) {
        char *token = strsep(&cursor, ",");
        int cpu = parse_cpu_id(token);
        if (cpu < 0 || CPU_ISSET(cpu, set)) {
            free(copy);
            return -1;
        }
        CPU_SET(cpu, set);
    }
    free(copy);
    return 0;
}

static int affinity_equals(const cpu_set_t *expected) {
    cpu_set_t actual;

    CPU_ZERO(&actual);
    if (sched_getaffinity(0, sizeof(actual), &actual) != 0) {
        fprintf(stderr, "selftest: sched_getaffinity: %s\n", strerror(errno));
        return 0;
    }
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        if (CPU_ISSET(cpu, &actual) != CPU_ISSET(cpu, expected)) {
            return 0;
        }
    }
    return 1;
}

static int run_enabled_exec_chain(void) {
    pid_t child = fork();
    int status;

    if (child < 0) {
        fprintf(stderr, "selftest: fork for exec-chain test: %s\n", strerror(errno));
        return 0;
    }
    if (child == 0) {
        /* The shell then /bin/true each reload the shim with the support-only
         * affinity inherited from their parent. Both constructors must be
         * able to check the full cgroup-allowed union before pinning back. */
        execl("/bin/sh", "sh", "-c", "exec /bin/true", (char *) NULL);
        _exit(127);
    }
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) {
            fprintf(stderr, "selftest: waitpid for exec-chain test: %s\n",
                    strerror(errno));
            return 0;
        }
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        fprintf(stderr, "selftest: enabled exec chain failed (status=0x%x)\n",
                status);
        return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    static const char *const names[] = {
        "search-cpu-x",
        "search-io-x",
        "search-ioall-x",
    };
    pthread_t threads[sizeof(names) / sizeof(names[0])];
    struct worker_case workers[sizeof(names) / sizeof(names[0])];
    int pass_through = argc == 2 && strcmp(argv[1], "--pass-through") == 0;
    int expected_cpu = -1;

    if (pass_through) {
        if (getenv("BENCH_COMPUTE_CPU") != NULL ||
            getenv("BENCH_SUPPORT_CPUS") != NULL) {
            fprintf(stderr, "selftest: pass-through mode requires both benchmark variables unset\n");
            return 2;
        }
        if (parse_cpu_list(getenv("BENCH_EXPECTED_CPUSET"),
                           &expected_affinity) != 0) {
            return 2;
        }
        cpu_set_t main_affinity;
        CPU_ZERO(&main_affinity);
        if (sched_getaffinity(0, sizeof(main_affinity), &main_affinity) != 0) {
            fprintf(stderr, "selftest: sched_getaffinity: %s\n", strerror(errno));
            return 2;
        }
        for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
            if (CPU_ISSET(cpu, &main_affinity) != CPU_ISSET(cpu, &expected_affinity)) {
                fprintf(stderr, "selftest: preload changed main affinity in pass-through mode\n");
                return 2;
            }
        }
    } else {
        expected_cpu = parse_cpu_id(getenv("BENCH_COMPUTE_CPU"));
        if (expected_cpu < 0) {
            return 2;
        }
        if (parse_cpu_list(getenv("BENCH_SUPPORT_CPUS"), &expected_affinity) != 0) {
            fprintf(stderr, "selftest: BENCH_SUPPORT_CPUS must be a comma-separated cpuset\n");
            return 2;
        }
        if (!affinity_equals(&expected_affinity)) {
            fprintf(stderr, "selftest: preload did not pin main thread to BENCH_SUPPORT_CPUS\n");
            return 2;
        }
        CPU_ZERO(&expected_affinity);
        CPU_SET(expected_cpu, &expected_affinity);
    }
    atomic_init(&work_started, 0);

    for (size_t index = 0; index < sizeof(names) / sizeof(names[0]); ++index) {
        workers[index].name = names[index];
        workers[index].expected_cpu = expected_cpu;
        int result = pthread_create(&threads[index], NULL,
                                   check_named_worker, &workers[index]);
        if (result != 0) {
            fprintf(stderr, "selftest: pthread_create: %s\n", strerror(result));
            return 3;
        }
    }

    for (size_t index = 0; index < sizeof(names) / sizeof(names[0]); ++index) {
        void *result = NULL;
        int join_result = pthread_join(threads[index], &result);
        if (join_result != 0 || result != NULL) {
            fprintf(stderr, "selftest: worker join failed for %s\n", names[index]);
            return 4;
        }
    }

    if (atomic_load_explicit(&work_started, memory_order_acquire) !=
        (int) (sizeof(names) / sizeof(names[0]))) {
        fprintf(stderr, "selftest: not every worker reached work after pinning\n");
        return 5;
    }
    if (pass_through) {
        printf("PASS: absent benchmark variables left main and named-worker affinity unchanged\n");
    } else {
        if (!run_enabled_exec_chain()) {
            return 6;
        }
        printf("PASS: main thread used BENCH_SUPPORT_CPUS; all three named-worker prefixes were pinned before simulated work; support-only exec chain succeeded\n");
    }
    return 0;
}
