// Command measure_abis_payload_b1_typed_transport_top10_20261024 measures one
// B1 Qdrant search per HTTP request over exactly 1,024 manifest queries. Each
// request returns limit=10. Payload mode is pinned in the manifest: true
// validates every typed metadata field; false requires the payload field to
// be absent while still validating the complete ordered ID/score response.
//
// It is a standalone load client. It does not build Qdrant, call Docker, or
// create or modify cluster state.
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/tls"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"math/big"
	"net/http"
	"net/http/httptrace"
	"net/url"
	"os"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

const (
	manifestSchema          = "benchmark_abis_payload_b1_top10_go_manifest_v1"
	resultSchema            = "benchmark_abis_payload_b1_top10_go_http1_v1"
	maxResponseBytes        = 8 << 20
	maxScheduledRequests    = 100_000
	maxOfferedRate          = 2_000.0
	maxInflightLimit        = 160
	failureDetailLimit      = 50
	errorBodyPreviewLimit   = 4 << 10
	errorTextLimit          = 1 << 10
	errorEnvelopeParseLimit = 64 << 10
	retryAfterLimit         = 256
	expectedQueryCount      = 1_024
	expectedResultLimit     = 10
	defaultScoreTolerance   = 1e-6
)

type manifest struct {
	Schema              string          `json:"schema"`
	Endpoint            string          `json:"endpoint"`
	QueryCount          int             `json:"query_count"`
	ResultLimit         int             `json:"result_limit"`
	WithPayload         *bool           `json:"with_payload"`
	RequestBodiesBase64 []string        `json:"request_bodies_base64"`
	CandidateTruth      [][]truthHit    `json:"candidate_truth"`
	ExpectedSelected    []selectedTruth `json:"expected_selected"`
	Pins                json.RawMessage `json:"pins,omitempty"`
}

type truthHit struct {
	ID    json.RawMessage `json:"id"`
	Score json.RawMessage `json:"score"`
}

type typedTruthHit struct {
	ID    int64
	Score float64
}

type typedResponse struct {
	Result []typedHit `json:"result"`
	Status *string    `json:"status"`
	Time   *float64   `json:"time"`
}

type typedHit struct {
	ID       *int64          `json:"id"`
	Version  *int64          `json:"version,omitempty"`
	Score    *float64        `json:"score"`
	Payload  json.RawMessage `json:"payload,omitempty"`
	ShardKey json.RawMessage `json:"shard_key,omitempty"`
}

type typedPayload struct {
	ABIS       *typedABIS       `json:"abis"`
	Attributes *typedAttributes `json:"attributes"`
}

type typedABIS struct {
	Active               *bool   `json:"active"`
	BiometricRecordID    *string `json:"biometric_record_id"`
	CollectionID         *string `json:"collection_id"`
	ModelVersion         *string `json:"model_version"`
	NormalizationVersion *string `json:"normalization_version"`
	Operation            *string `json:"operation"`
	SubjectID            *string `json:"subject_id"`
}

type typedAttributes struct {
	Position *string `json:"position"`
	Status   *string `json:"status"`
}

// These structs deliberately keep canonical JSON key order. They reproduce the
// independent manifest's historical sorted-key metadata digest without maps.
type canonicalMetadataRow struct {
	ID      int64                    `json:"id"`
	Payload canonicalExpectedPayload `json:"payload"`
}

type canonicalExpectedPayload struct {
	ABIS       canonicalExpectedABIS       `json:"abis"`
	Attributes canonicalExpectedAttributes `json:"attributes"`
}

type canonicalExpectedABIS struct {
	Active               bool   `json:"active"`
	BiometricRecordID    string `json:"biometric_record_id"`
	CollectionID         string `json:"collection_id"`
	ModelVersion         string `json:"model_version"`
	NormalizationVersion string `json:"normalization_version"`
	Operation            string `json:"operation"`
	SubjectID            string `json:"subject_id"`
}

type canonicalExpectedAttributes struct {
	Position string `json:"position"`
	Status   string `json:"status"`
}

type selectedTruth struct {
	MetadataSHA256 string `json:"metadata_sha256"`
}

type config struct {
	endpoint       string
	apiKey         string
	bodies         [][]byte
	truth          [][]typedTruthHit
	selected       []selectedTruth
	resultLimit    int
	withPayload    bool
	rate           float64
	seconds        float64
	maxInflight    int
	timeout        time.Duration
	manifestHash   string
	manifestPins   json.RawMessage
	httpErrors     *httpErrorDiagnosticCollector
	mode           string
	concurrency    int
	scoreTolerance float64
}

type httpErrorDiagnostic struct {
	RequestIndex         int    `json:"request_index"`
	HTTPStatus           int    `json:"http_status"`
	CapturedBodySHA256   string `json:"captured_body_sha256"`
	CapturedBodyBytes    int    `json:"captured_body_bytes"`
	CapturedBodyComplete bool   `json:"captured_body_complete"`
	BodyPreview          string `json:"body_preview"`
	BodyPreviewTruncated bool   `json:"body_preview_truncated"`
	StatusErrorCaptured  bool   `json:"status_error_captured"`
	StatusError          string `json:"status_error"`
	StatusErrorTruncated bool   `json:"status_error_truncated"`
	RetryAfter           string `json:"retry_after"`
	RetryAfterTruncated  bool   `json:"retry_after_truncated"`
}

type errorDiags []httpErrorDiagnostic

// Keep diagnostics for the 50 lowest request indexes that received non-200
// responses. The mutex makes insertion race-safe; retaining the lowest indexes
// makes the selected set independent of completion order.
type httpErrorDiagnosticCollector struct {
	mu      sync.Mutex
	details map[int]httpErrorDiagnostic
}

func newHTTPErrorDiagnosticCollector() *httpErrorDiagnosticCollector {
	return &httpErrorDiagnosticCollector{details: make(map[int]httpErrorDiagnostic, failureDetailLimit)}
}

func (collector *httpErrorDiagnosticCollector) record(detail httpErrorDiagnostic) {
	if collector == nil {
		return
	}
	collector.mu.Lock()
	defer collector.mu.Unlock()
	if _, exists := collector.details[detail.RequestIndex]; exists {
		return
	}
	if len(collector.details) < failureDetailLimit {
		collector.details[detail.RequestIndex] = detail
		return
	}
	largestIndex := -1
	for index := range collector.details {
		if index > largestIndex {
			largestIndex = index
		}
	}
	if detail.RequestIndex < largestIndex {
		delete(collector.details, largestIndex)
		collector.details[detail.RequestIndex] = detail
	}
}

func (collector *httpErrorDiagnosticCollector) snapshot() []httpErrorDiagnostic {
	if collector == nil {
		return nil
	}
	collector.mu.Lock()
	defer collector.mu.Unlock()
	indices := make([]int, 0, len(collector.details))
	for index := range collector.details {
		indices = append(indices, index)
	}
	sort.Ints(indices)
	details := make([]httpErrorDiagnostic, 0, len(indices))
	for _, index := range indices {
		details = append(details, collector.details[index])
	}
	return details
}

func makeHTTPErrorDiagnostic(index, status int, retryAfter string, body []byte, complete bool) httpErrorDiagnostic {
	bodyHash := sha256.Sum256(body)
	preview, previewTruncated := boundedDiagnosticBytes(body, errorBodyPreviewLimit)
	statusError := ""
	statusErrorCaptured := false
	statusErrorTruncated := false
	if complete && len(body) <= errorEnvelopeParseLimit {
		var envelope struct {
			Status struct {
				Error json.RawMessage `json:"error"`
			} `json:"status"`
		}
		if json.Unmarshal(body, &envelope) == nil {
			var decodedError string
			if json.Unmarshal(envelope.Status.Error, &decodedError) == nil {
				statusErrorCaptured = true
				statusError, statusErrorTruncated = boundedDiagnosticText(decodedError, errorTextLimit)
			}
		}
	}
	retryAfter, retryAfterTruncated := boundedDiagnosticText(retryAfter, retryAfterLimit)
	return httpErrorDiagnostic{
		RequestIndex: index, HTTPStatus: status,
		CapturedBodySHA256: hex.EncodeToString(bodyHash[:]), CapturedBodyBytes: len(body),
		CapturedBodyComplete: complete, BodyPreview: preview,
		BodyPreviewTruncated: previewTruncated, StatusErrorCaptured: statusErrorCaptured,
		StatusError:          statusError,
		StatusErrorTruncated: statusErrorTruncated, RetryAfter: retryAfter,
		RetryAfterTruncated: retryAfterTruncated,
	}
}

func boundedDiagnosticText(value string, inputLimit int) (string, bool) {
	truncated := len(value) > inputLimit
	if truncated {
		value = value[:inputLimit]
	}
	return strings.ToValidUTF8(value, "\uFFFD"), truncated
}

func boundedDiagnosticBytes(value []byte, inputLimit int) (string, bool) {
	truncated := len(value) > inputLimit
	if truncated {
		value = value[:inputLimit]
	}
	return strings.ToValidUTF8(string(value), "\uFFFD"), truncated
}

type requestTrace struct {
	mu              sync.Mutex
	getConnAt       time.Time
	connectAt       time.Time
	connectionWait  time.Duration
	tcpConnect      time.Duration
	firstByte       time.Duration
	connectionReuse bool
	gotConnection   bool
	gotFirstByte    bool
}

func (trace *requestTrace) clientTrace(dispatched time.Time) *httptrace.ClientTrace {
	return &httptrace.ClientTrace{
		GetConn: func(string) {
			trace.mu.Lock()
			if trace.getConnAt.IsZero() {
				trace.getConnAt = time.Now()
			}
			trace.mu.Unlock()
		},
		GotConn: func(info httptrace.GotConnInfo) {
			trace.mu.Lock()
			if !trace.getConnAt.IsZero() && !trace.gotConnection {
				trace.connectionWait = time.Since(trace.getConnAt)
			}
			trace.connectionReuse = info.Reused
			trace.gotConnection = true
			trace.mu.Unlock()
		},
		ConnectStart: func(_, _ string) {
			trace.mu.Lock()
			if trace.connectAt.IsZero() {
				trace.connectAt = time.Now()
			}
			trace.mu.Unlock()
		},
		ConnectDone: func(_, _ string, _ error) {
			trace.mu.Lock()
			if !trace.connectAt.IsZero() {
				trace.tcpConnect += time.Since(trace.connectAt)
				trace.connectAt = time.Time{}
			}
			trace.mu.Unlock()
		},
		GotFirstResponseByte: func() {
			trace.mu.Lock()
			if !trace.gotFirstByte {
				trace.firstByte = time.Since(dispatched)
				trace.gotFirstByte = true
			}
			trace.mu.Unlock()
		},
	}
}

func (trace *requestTrace) attach(row *requestResult) {
	trace.mu.Lock()
	defer trace.mu.Unlock()
	if trace.gotConnection || !trace.getConnAt.IsZero() {
		wait := trace.connectionWait
		if !trace.gotConnection {
			wait = time.Since(trace.getConnAt)
		}
		acquireMS := durationMS(wait)
		connectMS := durationMS(trace.tcpConnect)
		poolWaitMS := math.Max(0, acquireMS-connectMS)
		row.ConnectionAcquireMS = &acquireMS
		row.TCPConnectMS = &connectMS
		row.EstimatedPoolWaitMS = &poolWaitMS
		row.ConnectionObserved = trace.gotConnection
		row.ConnectionReused = trace.gotConnection && trace.connectionReuse
	}
	if trace.gotFirstByte {
		firstByteMS := durationMS(trace.firstByte)
		row.TimeToFirstByteMS = &firstByteMS
	}
}

type requestResult struct {
	Index                int      `json:"request_index"`
	Dispatched           bool     `json:"-"`
	CapacityRejected     bool     `json:"-"`
	CompletedHTTP        bool     `json:"-"`
	Success              bool     `json:"-"`
	CandidateTruthMatch  bool     `json:"-"`
	PayloadContractMatch bool     `json:"-"`
	MetadataHashMatch    bool     `json:"-"`
	Status               int      `json:"-"`
	Protocol             string   `json:"-"`
	Failure              string   `json:"-"`
	DispatchOffsetS      float64  `json:"-"`
	CompletionOffsetS    float64  `json:"-"`
	EndToEndMS           float64  `json:"-"`
	FullBodyReceivedMS   *float64 `json:"-"`
	HeaderLatencyMS      *float64 `json:"-"`
	BodyReadMS           *float64 `json:"-"`
	ValidationMS         *float64 `json:"-"`
	ServerTimeMS         *float64 `json:"-"`
	ResponseBytes        int      `json:"-"`
	ConnectionAcquireMS  *float64 `json:"-"`
	EstimatedPoolWaitMS  *float64 `json:"-"`
	TCPConnectMS         *float64 `json:"-"`
	TimeToFirstByteMS    *float64 `json:"-"`
	ConnectionObserved   bool     `json:"-"`
	ConnectionReused     bool     `json:"-"`
	MismatchRank         *int     `json:"-"`
}

type latencySummary struct {
	Count  int      `json:"count"`
	P50MS  *float64 `json:"p50_ms"`
	P95MS  *float64 `json:"p95_ms"`
	P99MS  *float64 `json:"p99_ms"`
	MeanMS *float64 `json:"mean_ms"`
	MaxMS  *float64 `json:"max_ms"`
}

type byteSummary struct {
	Count int     `json:"count"`
	Min   int     `json:"min"`
	Mean  float64 `json:"mean"`
	Max   int     `json:"max"`
}

type failureDetail struct {
	RequestIndex int    `json:"request_index"`
	HTTPStatus   int    `json:"http_status,omitempty"`
	Failure      string `json:"failure"`
	Rank         *int   `json:"rank,omitempty"`
}

type report struct {
	Schema                        string            `json:"schema"`
	Scope                         string            `json:"scope"`
	Mode                          string            `json:"mode"`
	LoadShape                     string            `json:"load_shape"`
	StartedUTC                    string            `json:"started_utc"`
	ManifestSHA256                string            `json:"manifest_sha256"`
	ManifestPins                  json.RawMessage   `json:"manifest_pins,omitempty"`
	ExecutableSHA256              string            `json:"executable_sha256,omitempty"`
	ExecutableSHA256Error         string            `json:"executable_sha256_error,omitempty"`
	Endpoint                      string            `json:"endpoint"`
	RequestProtocol               string            `json:"request_protocol"`
	GoVersion                     string            `json:"go_version"`
	GOMAXPROCS                    int               `json:"gomaxprocs"`
	Transport                     transportEvidence `json:"transport"`
	Concurrency                   int               `json:"concurrency"`
	ConfiguredMaxInflight         int               `json:"configured_max_inflight"`
	OfferedRateHTTPRPS            float64           `json:"offered_rate_http_rps"`
	OfferedDurationS              float64           `json:"offered_duration_s"`
	DispatchWindowS               float64           `json:"dispatch_window_s"`
	ActualDispatchDurationS       float64           `json:"actual_dispatch_duration_s"`
	DrainDurationS                float64           `json:"drain_duration_s"`
	ThroughputBasis               string            `json:"throughput_basis"`
	RequestBodyCount              int               `json:"manifest_request_body_count"`
	WarmupRequests                int               `json:"warmup_requests"`
	WarmupSuccesses               int               `json:"warmup_successes"`
	CandidateTruthCount           int               `json:"candidate_truth_count_per_request"`
	ResultLimit                   int               `json:"result_limit"`
	WithPayload                   bool              `json:"with_payload"`
	PayloadContract               string            `json:"payload_validation_contract"`
	PayloadContractMatches        int               `json:"payload_contract_matches"`
	ExpectedMetadataSHA256        []string          `json:"expected_metadata_sha256"`
	ScoreTolerance                float64           `json:"score_tolerance"`
	MaxResponseBodyBytes          int               `json:"max_response_body_bytes"`
	PlannedRequests               int               `json:"planned_requests"`
	ClientCapacityRejections      int               `json:"client_capacity_rejections"`
	DispatchedRequests            int               `json:"dispatched_requests"`
	HTTPResponses                 int               `json:"http_responses"`
	SuccessfulRequests            int               `json:"successful_requests"`
	FailedRequests                int               `json:"failed_requests"`
	TransportTimeouts             int               `json:"transport_timeouts"`
	TransportFailures             int               `json:"transport_failures"`
	HTTPFailureRequests           int               `json:"http_failure_requests"`
	ExactCandidateTruth           int               `json:"exact_candidate_truth_matches"`
	ExactPayloadContract          int               `json:"exact_payload_contract_matches"`
	ExactMetadataHash             int               `json:"exact_metadata_hash_matches"`
	ActualElapsedS                float64           `json:"actual_elapsed_s"`
	SuccessfulCompletedHTTPRPS    float64           `json:"successful_completed_http_rps"`
	AllHTTPResponsesPerS          float64           `json:"all_http_responses_per_s"`
	PeakInflight                  int               `json:"peak_inflight"`
	FullClientLatencyMS           latencySummary    `json:"full_response_validated_latency_ms"`
	FullBodyReceived              latencySummary    `json:"dispatch_to_complete_http_response_body_received_ms"`
	SuccessfulFullBodyReceived    latencySummary    `json:"successful_dispatch_to_complete_http_response_body_received_ms"`
	HeaderLatencyMS               latencySummary    `json:"response_headers_latency_ms"`
	BodyReadMS                    latencySummary    `json:"response_body_read_duration_ms"`
	ValidationMS                  latencySummary    `json:"response_validation_duration_ms"`
	SuccessfulLatencyMS           latencySummary    `json:"successful_full_response_validated_latency_ms"`
	FailureLatencyMS              latencySummary    `json:"failed_full_response_validated_latency_ms"`
	ServerJSONTimeMS              latencySummary    `json:"server_json_time_ms"`
	ConnectionAcquireMS           latencySummary    `json:"connection_acquire_ms"`
	EstimatedPoolWaitMS           latencySummary    `json:"estimated_pool_wait_ms"`
	TCPConnectMS                  latencySummary    `json:"tcp_connect_ms"`
	TimeToFirstByteMS             latencySummary    `json:"time_to_first_byte_ms"`
	ResponseBytes                 byteSummary       `json:"response_body_bytes"`
	ReusedConnections             int               `json:"reused_connections"`
	NewConnections                int               `json:"new_connections"`
	SuccessfulBySecond            map[string]int    `json:"successful_completions_by_elapsed_second"`
	HTTPResponsesBySecond         map[string]int    `json:"http_responses_by_elapsed_second"`
	HTTPStatusCounts              map[string]int    `json:"http_status_counts"`
	ResponseProtocolCounts        map[string]int    `json:"response_protocol_counts"`
	FailureCounts                 map[string]int    `json:"failure_counts"`
	FailureDetails                []failureDetail   `json:"failure_details"`
	FailureDetailsOmitted         int               `json:"failure_details_omitted"`
	HTTPErrorDiagnostics          errorDiags        `json:"http_error_diagnostics,omitempty"`
	QuantileMethod                string            `json:"quantile_method"`
	MetadataHashMethod            string            `json:"metadata_hash_method"`
	APIKeyHandling                string            `json:"api_key_handling"`
	RawRequestsOrPayloadsIncluded bool              `json:"raw_requests_or_payloads_included"`
}

type transportEvidence struct {
	HTTP2Disabled        bool `json:"http2_disabled"`
	ProxyDisabled        bool `json:"proxy_disabled"`
	MaxConnsPerHost      int  `json:"max_conns_per_host"`
	MaxIdleConns         int  `json:"max_idle_conns"`
	MaxIdleConnsPerHost  int  `json:"max_idle_conns_per_host"`
	MaxResponseBodyBytes int  `json:"max_response_body_bytes"`
	RedirectsFollowed    bool `json:"redirects_followed"`
	CompressionDisabled  bool `json:"compression_disabled"`
}

type manifestValidationSummary struct {
	Schema         string `json:"schema"`
	Status         string `json:"status"`
	ManifestSHA256 string `json:"manifest_sha256"`
	QueryCount     int    `json:"query_count"`
	ResultLimit    int    `json:"result_limit"`
	WithPayload    bool   `json:"with_payload"`
}

func main() {
	manifestPath := flag.String("manifest", "", "Top10 B1 manifest JSON path (required)")
	validateManifestOnly := flag.Bool("validate-manifest-only", false, "validate the complete manifest and print its pins without reading API credentials or making requests")
	outputPath := flag.String("output", "", "write JSON report here (default stdout)")
	mode := flag.String("mode", "closed-loop", "closed-loop or open-loop")
	concurrency := flag.Int("concurrency", 1, "fixed worker count for closed-loop; also max inflight if not supplied")
	rate := flag.Float64("rate", 0, "offered HTTP RPS (required for open-loop)")
	seconds := flag.Float64("seconds", 60, "measured dispatch window in seconds")
	maxInflight := flag.Int("max-inflight", 0, "max simultaneous requests; defaults to concurrency (closed-loop) or 160 (open-loop)")
	timeout := flag.Duration("timeout", 30*time.Second, "per-request timeout including response body read")
	apiKeyEnv := flag.String("api-key-env", "QDRANT_API_KEY", "environment variable holding the API key")
	goMaxProcs := flag.Int("gomaxprocs", 2, "Go scheduler threads")
	warmupRequests := flag.Int("warmup-requests", 0, "successful full-response warmup requests excluded from measurement")
	scoreTolerance := flag.Float64("score-tolerance", defaultScoreTolerance, "maximum absolute candidate score difference")
	flag.Parse()

	if *manifestPath == "" {
		fatalf("--manifest is required")
	}
	if *validateManifestOnly {
		if err := runManifestValidationOnly(*manifestPath, *outputPath); err != nil {
			fatalf("manifest validation: %v", err)
		}
		return
	}
	if *mode != "closed-loop" && *mode != "open-loop" {
		fatalf("--mode must be closed-loop or open-loop")
	}
	if *seconds <= 0 || math.IsNaN(*seconds) || math.IsInf(*seconds, 0) {
		fatalf("--seconds must be finite and positive")
	}
	if *timeout <= 0 {
		fatalf("--timeout must be positive")
	}
	if *goMaxProcs < 1 || *goMaxProcs > 128 {
		fatalf("--gomaxprocs must be in 1..128")
	}
	if *warmupRequests < 0 || *warmupRequests > 256 {
		fatalf("--warmup-requests must be in 0..256")
	}
	if *scoreTolerance < 0 || math.IsNaN(*scoreTolerance) || math.IsInf(*scoreTolerance, 0) {
		fatalf("--score-tolerance must be finite and nonnegative")
	}
	if *maxInflight == 0 {
		if *mode == "closed-loop" {
			*maxInflight = *concurrency
		} else {
			*maxInflight = maxInflightLimit
		}
	}
	if *maxInflight < 1 || *maxInflight > maxInflightLimit {
		fatalf("--max-inflight must be in 1..%d", maxInflightLimit)
	}
	if *mode == "closed-loop" {
		if *concurrency < 1 || *concurrency > maxInflightLimit {
			fatalf("--concurrency must be in 1..%d", maxInflightLimit)
		}
		if *maxInflight < *concurrency {
			fatalf("--max-inflight must be >= --concurrency")
		}
	} else {
		if *rate <= 0 || *rate > maxOfferedRate || math.IsNaN(*rate) || math.IsInf(*rate, 0) {
			fatalf("open-loop --rate must be finite and in (0, %.0f]", maxOfferedRate)
		}
		if *rate**seconds > maxScheduledRequests {
			fatalf("open-loop rate*seconds exceeds %d scheduled requests", maxScheduledRequests)
		}
	}
	reportedConcurrency := *concurrency
	if *mode == "open-loop" {
		reportedConcurrency = 0
	}

	loaded, manifestHash, bodies, truth, selected, err := loadAndValidateManifest(*manifestPath)
	if err != nil {
		fatalf("manifest: %v", err)
	}
	u, err := validateEndpoint(loaded.Endpoint)
	if err != nil {
		fatalf("endpoint: %v", err)
	}
	apiKey := os.Getenv(*apiKeyEnv)
	if apiKey == "" {
		fatalf("API key environment variable %q is empty or unset", *apiKeyEnv)
	}
	runtime.GOMAXPROCS(*goMaxProcs)

	cfg := config{
		endpoint: u.String(), apiKey: apiKey, bodies: bodies, truth: truth,
		selected: selected, resultLimit: loaded.ResultLimit, withPayload: *loaded.WithPayload,
		rate: *rate, seconds: *seconds,
		maxInflight: *maxInflight, timeout: *timeout,
		manifestHash: manifestHash, manifestPins: loaded.Pins,
		mode: *mode, concurrency: reportedConcurrency,
		scoreTolerance: *scoreTolerance,
	}
	client, transport := newHTTPClient(cfg.maxInflight)
	defer transport.CloseIdleConnections()

	warmupSuccesses, completedWarmupRequests, err := runWarmup(context.Background(), client, cfg, *warmupRequests)
	if err != nil {
		fatalf("warmup: %v", err)
	}
	cfg.httpErrors = newHTTPErrorDiagnosticCollector()

	var results []requestResult
	var started time.Time
	var peakInflight int
	var plannedRequests int
	if cfg.mode == "closed-loop" {
		results, started, peakInflight, err = runClosedLoop(context.Background(), client, cfg)
		if err != nil {
			fatalf("closed-loop run: %v", err)
		}
		plannedRequests = len(results)
	} else {
		results, started, peakInflight, plannedRequests, err = runOpenLoop(context.Background(), client, cfg)
		if err != nil {
			fatalf("open-loop run: %v", err)
		}
	}
	doc, err := summarize(cfg, results, started, peakInflight, plannedRequests, completedWarmupRequests, warmupSuccesses)
	if err != nil {
		fatalf("summarize: %v", err)
	}
	encoded, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		fatalf("encode report: %v", err)
	}
	if err := writeOutput(*outputPath, append(encoded, '\n')); err != nil {
		fatalf("write report: %v", err)
	}
	if doc.FailedRequests > 0 || doc.ClientCapacityRejections > 0 {
		os.Exit(1)
	}
}

func runManifestValidationOnly(manifestPath, outputPath string) error {
	loaded, manifestHash, bodies, _, _, err := loadAndValidateManifest(manifestPath)
	if err != nil {
		return err
	}
	summary := manifestValidationSummary{
		Schema: "benchmark_abis_payload_b1_top10_manifest_validation_v1",
		Status: "VALIDATED", ManifestSHA256: manifestHash,
		QueryCount: len(bodies), ResultLimit: loaded.ResultLimit,
		WithPayload: *loaded.WithPayload,
	}
	encoded, err := json.MarshalIndent(summary, "", "  ")
	if err != nil {
		return err
	}
	return writeOutput(outputPath, append(encoded, '\n'))
}

func loadAndValidateManifest(path string) (manifest, string, [][]byte, [][]typedTruthHit, []selectedTruth, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	hash := sha256.Sum256(raw)
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	var value manifest
	if err := decoder.Decode(&value); err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		if err == nil {
			return manifest{}, "", nil, nil, nil, errors.New("manifest has trailing JSON data")
		}
		return manifest{}, "", nil, nil, nil, err
	}
	if value.Schema != manifestSchema {
		return manifest{}, "", nil, nil, nil, fmt.Errorf("schema must be %q", manifestSchema)
	}
	if value.QueryCount != expectedQueryCount || value.ResultLimit != expectedResultLimit || value.WithPayload == nil {
		return manifest{}, "", nil, nil, nil, fmt.Errorf("query_count must be %d, result_limit must be %d, and with_payload must be present", expectedQueryCount, expectedResultLimit)
	}
	if len(value.Pins) > 0 && !json.Valid(value.Pins) {
		return manifest{}, "", nil, nil, nil, errors.New("pins must contain valid JSON")
	}
	if len(value.RequestBodiesBase64) != expectedQueryCount {
		return manifest{}, "", nil, nil, nil, fmt.Errorf("request_bodies_base64 must contain exactly %d rows", expectedQueryCount)
	}
	if len(value.RequestBodiesBase64) != len(value.CandidateTruth) ||
		len(value.RequestBodiesBase64) != len(value.ExpectedSelected) {
		return manifest{}, "", nil, nil, nil, errors.New("request bodies, candidate truth, and expected_selected counts differ")
	}
	if err := validatePinnedTop10Contract(value.Pins, value.QueryCount, value.ResultLimit, *value.WithPayload); err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	bodies := make([][]byte, len(value.RequestBodiesBase64))
	truth := make([][]typedTruthHit, len(value.CandidateTruth))
	filterMode := ""
	for i, encoded := range value.RequestBodiesBase64 {
		body, err := base64.StdEncoding.DecodeString(encoded)
		if err != nil || len(body) == 0 || !json.Valid(body) {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("request body %d is invalid base64 or JSON", i)
		}
		if err := validateRequestBody(body, value.ResultLimit, *value.WithPayload); err != nil {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("request body %d: %w", i, err)
		}
		thisFilterMode, err := requestFilterMode(body)
		if err != nil {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("request body %d filter: %w", i, err)
		}
		if filterMode == "" {
			filterMode = thisFilterMode
		} else if thisFilterMode != filterMode {
			return manifest{}, "", nil, nil, nil, errors.New("all request bodies must use the same filter mode")
		}
		bodies[i] = body
		if len(value.CandidateTruth[i]) != value.ResultLimit {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("candidate_truth[%d] must contain exactly %d hits", i, value.ResultLimit)
		}
		seen := make(map[int64]struct{}, value.ResultLimit)
		truth[i] = make([]typedTruthHit, value.ResultLimit)
		for rank, hit := range value.CandidateTruth[i] {
			id, err := parseNumericPointID(hit.ID)
			if err != nil {
				return manifest{}, "", nil, nil, nil, fmt.Errorf("candidate_truth[%d][%d].id: %w", i, rank, err)
			}
			if _, exists := seen[id]; exists {
				return manifest{}, "", nil, nil, nil, fmt.Errorf("candidate_truth[%d] contains a duplicate ID", i)
			}
			seen[id] = struct{}{}
			score, err := parseFiniteNumber(hit.Score)
			if err != nil {
				return manifest{}, "", nil, nil, nil, fmt.Errorf("candidate_truth[%d][%d].score: %w", i, rank, err)
			}
			truth[i][rank] = typedTruthHit{ID: id, Score: score}
		}
		if len(value.ExpectedSelected[i].MetadataSHA256) != sha256.Size*2 {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("expected_selected[%d].metadata_sha256 must be a SHA-256 hex digest", i)
		}
		if _, err := hex.DecodeString(value.ExpectedSelected[i].MetadataSHA256); err != nil {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("expected_selected[%d].metadata_sha256 is not hex", i)
		}
		derived, err := expectedMetadataSHA256(truth[i])
		if err != nil || !strings.EqualFold(derived, value.ExpectedSelected[i].MetadataSHA256) {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("expected_selected[%d].metadata_sha256 disagrees with candidate IDs and deterministic payload schema", i)
		}
	}
	if err := validatePinnedFilterMode(value.Pins, filterMode); err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	if _, err := validateEndpoint(value.Endpoint); err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	return value, hex.EncodeToString(hash[:]), bodies, truth, value.ExpectedSelected, nil
}

func parseNumericPointID(raw json.RawMessage) (int64, error) {
	var id int64
	if len(raw) == 0 || json.Unmarshal(raw, &id) != nil || id < 0 || id >= 3_000_000 {
		return 0, errors.New("ID must be a numeric point ID in [0, 3000000)")
	}
	return id, nil
}

func expectedPayload(id int64) canonicalExpectedPayload {
	active := (id/10)%10 != 0
	status := "inactive"
	if active {
		status = "active"
	}
	positions := [...]string{"left_thumb", "left_index", "left_middle", "left_ring", "left_little", "right_thumb", "right_index", "right_middle", "right_ring", "right_little"}
	return canonicalExpectedPayload{
		ABIS: canonicalExpectedABIS{
			Active:               active,
			BiometricRecordID:    fmt.Sprintf("00000001-0000-4000-8000-%012x", id),
			CollectionID:         "00000002-0000-4000-8000-000000000001",
			ModelVersion:         "gaussian-512-bench-v1",
			NormalizationVersion: "cosine-l2-f32-v1",
			Operation:            "upsert",
			SubjectID:            fmt.Sprintf("00000000-0000-4000-8000-%012x", id/10),
		},
		Attributes: canonicalExpectedAttributes{Position: positions[id%10], Status: status},
	}
}

func expectedMetadataSHA256(truth []typedTruthHit) (string, error) {
	rows := make([]canonicalMetadataRow, len(truth))
	for i, hit := range truth {
		rows[i] = canonicalMetadataRow{ID: hit.ID, Payload: expectedPayload(hit.ID)}
	}
	encoded, err := json.Marshal(rows)
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256(encoded)
	return hex.EncodeToString(digest[:]), nil
}

func requestFilterMode(body []byte) (string, error) {
	var top map[string]json.RawMessage
	if err := json.Unmarshal(body, &top); err != nil {
		return "", err
	}
	search := json.RawMessage(body)
	if raw, ok := top["searches"]; ok {
		var searches []json.RawMessage
		if err := json.Unmarshal(raw, &searches); err != nil || len(searches) != 1 {
			return "", errors.New("searches must contain exactly one row")
		}
		search = searches[0]
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(search, &fields); err != nil {
		return "", errors.New("search must be an object")
	}
	raw, ok := fields["filter"]
	if !ok {
		return "unfiltered", nil
	}
	return supportedFilterMode(raw)
}

func supportedFilterMode(raw json.RawMessage) (string, error) {
	if err := validateFilter(raw); err != nil {
		return "", err
	}
	var filter map[string]json.RawMessage
	if err := json.Unmarshal(raw, &filter); err != nil {
		return "", err
	}
	var must []json.RawMessage
	if err := json.Unmarshal(filter["must"], &must); err != nil {
		return "", err
	}
	position := ""
	positionSeen := false
	for _, clause := range must {
		key, value, err := matchClause(clause)
		if err != nil {
			return "", err
		}
		if key == "attributes.position" {
			positionSeen = true
			if err := json.Unmarshal(value, &position); err != nil {
				return "", errors.New("position filter must be a string")
			}
		}
	}
	if !positionSeen {
		if _, hasMustNot := filter["must_not"]; hasMustNot {
			return "", errors.New("active-only filter must not include must_not")
		}
		return "active_only", nil
	}
	if position != "left_index" {
		return "", errors.New("supported position filter must be attributes.position=left_index")
	}
	var mustNot []json.RawMessage
	if err := json.Unmarshal(filter["must_not"], &mustNot); err != nil || len(mustNot) != 1 {
		return "", errors.New("selective filter must exclude exactly one subject_id")
	}
	key, value, err := matchClause(mustNot[0])
	if err != nil || key != "abis.subject_id" {
		return "", errors.New("selective filter must exclude abis.subject_id")
	}
	var subject string
	if err := json.Unmarshal(value, &subject); err != nil || subject != "00000000-0000-4000-8000-000000000001" {
		return "", errors.New("selective filter must exclude the benchmark subject_id")
	}
	return "active_position_exclude", nil
}

func validatePinnedFilterMode(pins json.RawMessage, requestMode string) error {
	if len(pins) == 0 {
		return nil
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(pins, &fields); err != nil || fields == nil {
		return errors.New("manifest pins must be a JSON object")
	}
	raw, ok := fields["filter"]
	if !ok {
		return errors.New("manifest pins.filter is required")
	}
	pinnedMode := "unfiltered"
	if !bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
		var err error
		pinnedMode, err = supportedFilterMode(raw)
		if err != nil {
			return fmt.Errorf("manifest pins.filter: %w", err)
		}
	}
	if pinnedMode != requestMode {
		return fmt.Errorf("manifest pins.filter mode %q does not match request mode %q", pinnedMode, requestMode)
	}
	return nil
}

func validatePinnedTop10Contract(pins json.RawMessage, queryCount, resultLimit int, withPayload bool) error {
	if len(pins) == 0 {
		return errors.New("manifest pins are required")
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(pins, &fields); err != nil || fields == nil {
		return errors.New("manifest pins must be a JSON object")
	}
	var pinnedQueryCount, pinnedResultLimit int
	if err := json.Unmarshal(fields["query_count"], &pinnedQueryCount); err != nil || pinnedQueryCount != queryCount {
		return errors.New("manifest pins.query_count must match the 1,024 request rows")
	}
	if err := json.Unmarshal(fields["result_limit"], &pinnedResultLimit); err != nil || pinnedResultLimit != resultLimit {
		return errors.New("manifest pins.result_limit must match the Top10 result limit")
	}
	var pinnedWithPayload bool
	if err := json.Unmarshal(fields["with_payload"], &pinnedWithPayload); err != nil || pinnedWithPayload != withPayload {
		return errors.New("manifest pins.with_payload must match the selected payload mode")
	}
	return nil
}

func validateRequestBody(body []byte, resultLimit int, withPayload bool) error {
	var top map[string]json.RawMessage
	if err := json.Unmarshal(body, &top); err != nil || len(top) == 0 {
		return errors.New("must be a JSON object")
	}
	var searches []json.RawMessage
	if raw, exists := top["searches"]; exists {
		if err := json.Unmarshal(raw, &searches); err != nil || len(searches) != 1 {
			return errors.New("B1 batch request must contain exactly one search")
		}
		return validateSearch(searches[0], resultLimit, withPayload)
	}
	return validateSearch(body, resultLimit, withPayload)
}

func validateSearch(raw json.RawMessage, resultLimit int, withPayload bool) error {
	var search map[string]json.RawMessage
	if err := json.Unmarshal(raw, &search); err != nil || len(search) == 0 {
		return errors.New("search must be a JSON object")
	}
	var limit int
	if err := json.Unmarshal(search["limit"], &limit); err != nil || limit != resultLimit {
		return fmt.Errorf("limit must be %d", resultLimit)
	}
	if withPayload && !rawIsTrue(search["with_payload"]) {
		return errors.New("with_payload must be true")
	}
	if !withPayload && !rawIsFalse(search["with_payload"]) {
		return errors.New("with_payload must be false")
	}
	if !rawIsFalse(search["with_vector"]) {
		return errors.New("with_vector must be false")
	}
	if err := validateVector(search["vector"]); err != nil {
		return err
	}
	if raw, exists := search["filter"]; exists {
		if _, err := supportedFilterMode(raw); err != nil {
			return fmt.Errorf("filter is outside the supported B1 workload contract: %w", err)
		}
	}
	var params map[string]json.RawMessage
	if err := json.Unmarshal(search["params"], &params); err != nil || !rawIsFalse(params["exact"]) {
		return errors.New("params.exact must be false")
	}
	var quantization map[string]json.RawMessage
	if err := json.Unmarshal(params["quantization"], &quantization); err != nil ||
		!rawIsTrue(quantization["rescore"]) || !rawIsFalse(quantization["ignore"]) {
		return errors.New("params.quantization must specify rescore=true and ignore=false")
	}
	return nil
}

func validateVector(raw json.RawMessage) error {
	var vector map[string]json.RawMessage
	if err := json.Unmarshal(raw, &vector); err != nil {
		return errors.New("vector must be a named 512-dimensional vector")
	}
	var name string
	if err := json.Unmarshal(vector["name"], &name); err != nil || name == "" {
		return errors.New("vector.name must be present")
	}
	var values []json.RawMessage
	if err := json.Unmarshal(vector["vector"], &values); err != nil || len(values) != 512 {
		return errors.New("vector.vector must contain exactly 512 numbers")
	}
	for i, rawValue := range values {
		if _, err := parseFiniteNumber(rawValue); err != nil {
			return fmt.Errorf("vector.vector[%d] is not a finite number", i)
		}
	}
	return nil
}

func validateFilter(raw json.RawMessage) error {
	var filter map[string]json.RawMessage
	if err := json.Unmarshal(raw, &filter); err != nil || len(filter) == 0 {
		return errors.New("filter must be a nonempty object")
	}
	for key := range filter {
		if key != "must" && key != "must_not" {
			return fmt.Errorf("filter key %q is outside the ABIS B1 contract", key)
		}
	}
	var must []json.RawMessage
	if err := json.Unmarshal(filter["must"], &must); err != nil || len(must) < 1 || len(must) > 2 {
		return errors.New("filter.must must contain the active predicate and optional position predicate")
	}
	seen := map[string]bool{}
	for _, rawClause := range must {
		key, value, err := matchClause(rawClause)
		if err != nil {
			return err
		}
		if seen[key] {
			return fmt.Errorf("duplicate filter predicate %q", key)
		}
		seen[key] = true
		switch key {
		case "abis.active":
			if !rawIsTrue(value) {
				return errors.New("abis.active must match true")
			}
		case "attributes.position":
			if !isJSONScalar(value) {
				return errors.New("attributes.position match value must be a scalar")
			}
		default:
			return fmt.Errorf("unsupported filter.must key %q", key)
		}
	}
	if !seen["abis.active"] {
		return errors.New("filter.must must include abis.active=true")
	}
	var mustNot []json.RawMessage
	if raw, ok := filter["must_not"]; ok {
		if err := json.Unmarshal(raw, &mustNot); err != nil || len(mustNot) != 1 {
			return errors.New("filter.must_not must contain one abis.subject_id predicate")
		}
		key, value, err := matchClause(mustNot[0])
		if err != nil {
			return err
		}
		if key != "abis.subject_id" || !isJSONString(value) {
			return errors.New("filter.must_not must match one string value at abis.subject_id")
		}
	}
	if seen["attributes.position"] && len(mustNot) != 1 {
		return errors.New("selective filter must combine attributes.position with must_not abis.subject_id")
	}
	if !seen["attributes.position"] && len(mustNot) != 0 {
		return errors.New("broad active-only filter must not include must_not")
	}
	return nil
}

func matchClause(raw json.RawMessage) (string, json.RawMessage, error) {
	var clause map[string]json.RawMessage
	if err := json.Unmarshal(raw, &clause); err != nil || len(clause) != 2 {
		return "", nil, errors.New("filter clause must contain key and match")
	}
	var key string
	if err := json.Unmarshal(clause["key"], &key); err != nil || key == "" {
		return "", nil, errors.New("filter clause key is missing")
	}
	var match map[string]json.RawMessage
	if err := json.Unmarshal(clause["match"], &match); err != nil || len(match) != 1 {
		return "", nil, errors.New("filter clause must use exactly one match.value")
	}
	value, ok := match["value"]
	if !ok || !isJSONScalar(value) {
		return "", nil, errors.New("filter match.value must be a non-null scalar")
	}
	return key, value, nil
}

func rawIsTrue(raw json.RawMessage) bool  { return bytes.Equal(bytes.TrimSpace(raw), []byte("true")) }
func rawIsFalse(raw json.RawMessage) bool { return bytes.Equal(bytes.TrimSpace(raw), []byte("false")) }

func isJSONString(raw json.RawMessage) bool {
	var value string
	return json.Unmarshal(raw, &value) == nil
}

func isJSONScalar(raw json.RawMessage) bool {
	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 || bytes.Equal(trimmed, []byte("null")) {
		return false
	}
	var value any
	decoder := json.NewDecoder(bytes.NewReader(trimmed))
	decoder.UseNumber()
	if decoder.Decode(&value) != nil {
		return false
	}
	switch value.(type) {
	case string, bool, json.Number:
		return true
	default:
		return false
	}
}

func validateEndpoint(endpoint string) (*url.URL, error) {
	u, err := url.Parse(endpoint)
	if err != nil {
		return nil, err
	}
	if (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return nil, errors.New("endpoint must be an absolute HTTP(S) URL")
	}
	if u.User != nil || u.Fragment != "" {
		return nil, errors.New("endpoint must not include user info or a fragment")
	}
	if u.RawQuery != "" {
		query, err := url.ParseQuery(u.RawQuery)
		if err != nil || len(query) != 1 || len(query["consistency"]) != 1 || query.Get("consistency") != "quorum" {
			return nil, errors.New("only consistency=quorum is allowed in endpoint query")
		}
	}
	return u, nil
}

func canonicalID(raw json.RawMessage) (string, error) {
	if len(raw) == 0 {
		return "", errors.New("ID is missing")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return "", errors.New("ID is invalid JSON")
	}
	switch id := value.(type) {
	case string:
		return "s:" + id, nil
	case json.Number:
		integer, ok := new(big.Int).SetString(string(id), 10)
		if !ok || integer.Sign() < 0 {
			return "", errors.New("numeric IDs must be nonnegative integers")
		}
		return "n:" + integer.String(), nil
	default:
		return "", errors.New("ID must be a string or a nonnegative integer")
	}
}

func parseFiniteNumber(raw json.RawMessage) (float64, error) {
	var number json.Number
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return 0, err
	}
	var ok bool
	number, ok = value.(json.Number)
	if !ok {
		return 0, errors.New("value is not a number")
	}
	f, err := number.Float64()
	if err != nil || math.IsNaN(f) || math.IsInf(f, 0) {
		return 0, errors.New("number is not finite")
	}
	return f, nil
}

func newHTTPClient(maxInflight int) (*http.Client, *http.Transport) {
	transport := &http.Transport{
		Proxy:                 nil,
		MaxConnsPerHost:       maxInflight,
		MaxIdleConns:          maxInflight,
		MaxIdleConnsPerHost:   maxInflight,
		IdleConnTimeout:       30 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ExpectContinueTimeout: time.Second,
		ForceAttemptHTTP2:     false,
		TLSNextProto:          map[string]func(string, *tls.Conn) http.RoundTripper{},
		DisableCompression:    true,
	}
	client := &http.Client{
		Transport: transport,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	return client, transport
}

func runWarmup(parent context.Context, client *http.Client, cfg config, count int) (int, int, error) {
	if count == 0 {
		return 0, 0, nil
	}
	var started = time.Now()
	rows := make([]requestResult, count)
	semaphore := make(chan struct{}, cfg.maxInflight)
	var wait sync.WaitGroup
	for i := 0; i < count; i++ {
		semaphore <- struct{}{}
		wait.Add(1)
		go func(index int) {
			defer wait.Done()
			defer func() { <-semaphore }()
			rows[index] = executeRequest(parent, client, cfg, index, started)
		}(i)
	}
	wait.Wait()
	successes := 0
	for i, row := range rows {
		if !row.Success {
			return successes, count, fmt.Errorf("warmup request %d failed: %s", i, row.Failure)
		}
		successes++
	}
	return successes, count, nil
}

func runClosedLoop(parent context.Context, client *http.Client, cfg config) ([]requestResult, time.Time, int, error) {
	ready := sync.WaitGroup{}
	ready.Add(cfg.concurrency)
	startGate := make(chan struct{})
	workerRows := make([][]requestResult, cfg.concurrency)
	var workers sync.WaitGroup
	var nextIndex atomic.Int64
	var active atomic.Int64
	var peak atomic.Int64
	var started, deadline time.Time

	for worker := 0; worker < cfg.concurrency; worker++ {
		workers.Add(1)
		go func(workerIndex int) {
			defer workers.Done()
			ready.Done()
			<-startGate
			for time.Now().Before(deadline) {
				requestIndex := int(nextIndex.Add(1) - 1)
				activeNow := active.Add(1)
				for old := peak.Load(); activeNow > old && !peak.CompareAndSwap(old, activeNow); old = peak.Load() {
				}
				row := executeRequest(parent, client, cfg, requestIndex, started)
				active.Add(-1)
				workerRows[workerIndex] = append(workerRows[workerIndex], row)
			}
		}(worker)
	}
	ready.Wait()
	started = time.Now()
	deadline = started.Add(time.Duration(cfg.seconds * float64(time.Second)))
	close(startGate)
	workers.Wait()
	results := make([]requestResult, 0)
	for _, rows := range workerRows {
		results = append(results, rows...)
	}
	if len(results) == 0 {
		return nil, started, 0, errors.New("dispatch window elapsed before a request was dispatched")
	}
	return results, started, int(peak.Load()), nil
}

func runOpenLoop(parent context.Context, client *http.Client, cfg config) ([]requestResult, time.Time, int, int, error) {
	planned := int(math.Ceil(cfg.rate * cfg.seconds))
	if planned < 1 {
		planned = 1
	}
	started := time.Now()
	results := make([]requestResult, planned)
	semaphore := make(chan struct{}, cfg.maxInflight)
	var wait sync.WaitGroup
	var active atomic.Int64
	var peak atomic.Int64
	for index := 0; index < planned; index++ {
		target := started.Add(time.Duration(float64(index) / cfg.rate * float64(time.Second)))
		if delay := time.Until(target); delay > 0 {
			time.Sleep(delay)
		}
		select {
		case semaphore <- struct{}{}:
			activeNow := active.Add(1)
			for old := peak.Load(); activeNow > old && !peak.CompareAndSwap(old, activeNow); old = peak.Load() {
			}
			wait.Add(1)
			go func(requestIndex int) {
				defer wait.Done()
				defer func() {
					active.Add(-1)
					<-semaphore
				}()
				results[requestIndex] = executeRequest(parent, client, cfg, requestIndex, started)
			}(index)
		default:
			now := time.Now()
			results[index] = requestResult{
				Index: index, CapacityRejected: true,
				DispatchOffsetS:   now.Sub(started).Seconds(),
				CompletionOffsetS: now.Sub(started).Seconds(),
			}
		}
	}
	wait.Wait()
	return results, started, int(peak.Load()), planned, nil
}

func executeRequest(parent context.Context, client *http.Client, cfg config, index int, started time.Time) requestResult {
	dispatched := time.Now()
	row := requestResult{
		Index: index, Dispatched: true,
		DispatchOffsetS: dispatched.Sub(started).Seconds(),
	}
	ctx, cancel := context.WithTimeout(parent, cfg.timeout)
	defer cancel()
	trace := &requestTrace{}
	ctx = httptrace.WithClientTrace(ctx, trace.clientTrace(dispatched))
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, cfg.endpoint,
		bytes.NewReader(cfg.bodies[index%len(cfg.bodies)]))
	if err != nil {
		return finishFailure(row, "request_build_error", dispatched, started)
	}
	request.Header.Set("api-key", cfg.apiKey)
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Accept", "application/json")

	response, err := client.Do(request)
	if err != nil {
		trace.attach(&row)
		failure := "request_error"
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(ctx.Err(), context.DeadlineExceeded) {
			failure = "timeout"
		}
		return finishFailure(row, failure, dispatched, started)
	}
	row.Status = response.StatusCode
	row.Protocol = response.Proto
	row.CompletedHTTP = true
	headerMS := durationMS(time.Since(dispatched))
	row.HeaderLatencyMS = &headerMS
	bodyStarted := time.Now()
	body, readErr := io.ReadAll(io.LimitReader(response.Body, maxResponseBytes+1))
	bodyReceivedAt := time.Now()
	if readErr == nil && len(body) <= maxResponseBytes {
		fullBodyReceivedMS := durationMS(bodyReceivedAt.Sub(dispatched))
		row.FullBodyReceivedMS = &fullBodyReceivedMS
	}
	bodyReadMS := durationMS(bodyReceivedAt.Sub(bodyStarted))
	row.BodyReadMS = &bodyReadMS
	row.ResponseBytes = len(body)
	closeErr := response.Body.Close()
	trace.attach(&row)
	if response.StatusCode != http.StatusOK {
		cfg.httpErrors.record(makeHTTPErrorDiagnostic(
			index, response.StatusCode, response.Header.Get("Retry-After"), body,
			readErr == nil && len(body) <= maxResponseBytes,
		))
	}
	if readErr != nil {
		row.Failure = "response_read_error"
		return finishResponse(row, dispatched, started)
	}
	if closeErr != nil {
		row.Failure = "response_close_error"
		return finishResponse(row, dispatched, started)
	}
	if len(body) > maxResponseBytes {
		row.Failure = "response_too_large"
		return finishResponse(row, dispatched, started)
	}
	if response.Proto != "HTTP/1.1" {
		row.Failure = "protocol_not_http_1_1"
		return finishResponse(row, dispatched, started)
	}
	if response.StatusCode != http.StatusOK {
		if response.StatusCode == http.StatusTooManyRequests {
			row.Failure = "capacity_shed_429"
		} else {
			row.Failure = "http_status_" + strconv.Itoa(response.StatusCode)
		}
		return finishResponse(row, dispatched, started)
	}
	validationStarted := time.Now()
	serverTimeMS, truthMatch, payloadContractMatch, metadataMatch, failure, rank := validateResponse(
		body, cfg.truth[index%len(cfg.truth)], cfg.selected[index%len(cfg.selected)],
		cfg.resultLimit, cfg.withPayload, cfg.scoreTolerance,
	)
	validationMS := durationMS(time.Since(validationStarted))
	row.ValidationMS = &validationMS
	row.ServerTimeMS = serverTimeMS
	row.CandidateTruthMatch = truthMatch
	row.PayloadContractMatch = payloadContractMatch
	row.MetadataHashMatch = metadataMatch
	row.MismatchRank = rank
	if failure != "" {
		row.Failure = failure
		return finishResponse(row, dispatched, started)
	}
	row.Success = true
	return finishResponse(row, dispatched, started)
}

func validateResponse(body []byte, truth []typedTruthHit, selected selectedTruth, resultLimit int, withPayload bool, tolerance float64) (*float64, bool, bool, bool, string, *int) {
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	var envelope typedResponse
	if err := decoder.Decode(&envelope); err != nil {
		return nil, false, false, false, "invalid_json_or_response_shape", nil
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return nil, false, false, false, "invalid_json_or_response_shape", nil
	}
	if envelope.Time == nil || math.IsNaN(*envelope.Time) || math.IsInf(*envelope.Time, 0) || *envelope.Time < 0 {
		return nil, false, false, false, "invalid_server_time", nil
	}
	serverTimeMS := 1_000 * *envelope.Time
	if envelope.Status == nil || *envelope.Status != "ok" {
		return &serverTimeMS, false, false, false, "invalid_response_status", nil
	}
	if len(envelope.Result) != resultLimit || len(truth) != resultLimit {
		return &serverTimeMS, false, false, false, "candidate_count_mismatch", nil
	}
	if len(selected.MetadataSHA256) != sha256.Size*2 {
		return &serverTimeMS, false, false, false, "invalid_expected_metadata_hash", nil
	}
	for rank := range envelope.Result {
		hit := &envelope.Result[rank]
		if hit.ID == nil || hit.Score == nil {
			return &serverTimeMS, false, false, false, "missing_id_or_score", intPointer(rank)
		}
		if *hit.ID != truth[rank].ID {
			return &serverTimeMS, false, false, false, "candidate_id_or_score_mismatch", intPointer(rank)
		}
		if math.IsNaN(*hit.Score) || math.IsInf(*hit.Score, 0) || math.Abs(*hit.Score-truth[rank].Score) > tolerance {
			return &serverTimeMS, false, false, false, "candidate_id_or_score_mismatch", intPointer(rank)
		}
	}
	for rank := range envelope.Result {
		hit := &envelope.Result[rank]
		if withPayload {
			payload, err := decodeTypedPayload(hit.Payload)
			if err != nil || !payloadMatchesID(payload, *hit.ID) {
				return &serverTimeMS, true, false, false, "missing_or_invalid_payload", intPointer(rank)
			}
		} else if len(hit.Payload) != 0 {
			// For with_payload=false, only an omitted field is accepted. Explicit
			// null is still a present payload value and violates the request mode.
			return &serverTimeMS, true, false, false, "unexpected_payload", intPointer(rank)
		}
	}
	if withPayload {
		// loadAndValidateManifest independently recomputed this digest from the
		// candidate truth IDs and canonical payload schema. Exact per-hit typed
		// comparisons above validate the same values without a response-side hash.
		return &serverTimeMS, true, true, true, "", nil
	}
	return &serverTimeMS, true, true, false, "", nil
}

func decodeTypedPayload(raw json.RawMessage) (*typedPayload, error) {
	if len(raw) == 0 {
		return nil, errors.New("payload field is absent")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	var payload typedPayload
	if err := decoder.Decode(&payload); err != nil {
		return nil, err
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		if err == nil {
			return nil, errors.New("payload has trailing JSON data")
		}
		return nil, err
	}
	return &payload, nil
}

func payloadContractDescription(withPayload bool) string {
	if withPayload {
		return "all 10 result rows must contain the full typed synthetic ABIS payload; every required field must match its numeric point ID and unknown fields are rejected"
	}
	return "all 10 result rows must omit payload entirely; explicit null or any payload object is rejected"
}

func metadataHashDescription(withPayload bool) string {
	if withPayload {
		return "Manifest SHA-256 is recomputed from ordered Top10 IDs and canonical deterministic payload fields; each response strictly decodes and checks every typed payload field plus ordered IDs and score tolerance"
	}
	return "Manifest SHA-256 is recomputed from ordered Top10 IDs and canonical deterministic payload fields as oracle provenance; responses are validated for ordered IDs, score tolerance, and complete payload absence, so no response metadata hash is claimed"
}

func payloadMatchesID(got *typedPayload, id int64) bool {
	if got == nil || got.ABIS == nil || got.Attributes == nil {
		return false
	}
	want := expectedPayload(id)
	a := got.ABIS
	if a.Active == nil || a.BiometricRecordID == nil || a.CollectionID == nil || a.ModelVersion == nil ||
		a.NormalizationVersion == nil || a.Operation == nil || a.SubjectID == nil {
		return false
	}
	if *a.Active != want.ABIS.Active || *a.BiometricRecordID != want.ABIS.BiometricRecordID ||
		*a.CollectionID != want.ABIS.CollectionID || *a.ModelVersion != want.ABIS.ModelVersion ||
		*a.NormalizationVersion != want.ABIS.NormalizationVersion || *a.Operation != want.ABIS.Operation ||
		*a.SubjectID != want.ABIS.SubjectID {
		return false
	}
	attrs := got.Attributes
	return attrs.Position != nil && attrs.Status != nil &&
		*attrs.Position == want.Attributes.Position && *attrs.Status == want.Attributes.Status
}

func unpackResults(raw json.RawMessage) ([]json.RawMessage, error) {
	var direct []json.RawMessage
	if err := json.Unmarshal(raw, &direct); err != nil {
		return nil, err
	}
	if len(direct) > 0 && bytes.HasPrefix(bytes.TrimSpace(direct[0]), []byte("[")) {
		if len(direct) != 1 {
			return nil, errors.New("batch result must contain exactly one result row")
		}
		var nested []json.RawMessage
		if err := json.Unmarshal(direct[0], &nested); err != nil {
			return nil, err
		}
		return nested, nil
	}
	return direct, nil
}

func decodeUseNumber(raw json.RawMessage) (any, error) {
	var value any
	err := decodeIntoUseNumber(raw, &value)
	return value, err
}

func decodeIntoUseNumber(raw json.RawMessage, destination any) error {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(destination); err != nil {
		return err
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return errors.New("trailing JSON after value")
	}
	return nil
}

func canonicalJSON(value any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	encoded := buffer.Bytes()
	return bytes.TrimSuffix(encoded, []byte("\n")), nil
}

func finishFailure(row requestResult, reason string, dispatched, started time.Time) requestResult {
	row.Failure = reason
	return finishResponse(row, dispatched, started)
}

func finishResponse(row requestResult, dispatched, started time.Time) requestResult {
	completed := time.Now()
	row.EndToEndMS = durationMS(completed.Sub(dispatched))
	row.CompletionOffsetS = completed.Sub(started).Seconds()
	return row
}

func summarize(cfg config, rows []requestResult, started time.Time, peak, planned, warmupRequests, warmupSuccesses int) (report, error) {
	if len(rows) == 0 {
		return report{}, errors.New("no requests were measured")
	}
	var elapsed, lastDispatch float64
	for _, row := range rows {
		if row.Dispatched || row.CapacityRejected {
			if row.CompletionOffsetS > elapsed {
				elapsed = row.CompletionOffsetS
			}
			if row.DispatchOffsetS > lastDispatch {
				lastDispatch = row.DispatchOffsetS
			}
		}
	}
	if elapsed <= 0 {
		return report{}, errors.New("no completion elapsed time was recorded")
	}
	drain := math.Max(0, elapsed-lastDispatch)
	latencies := make([]float64, 0, len(rows))
	fullBodyReceivedLatencies := make([]float64, 0, len(rows))
	successfulFullBodyReceivedLatencies := make([]float64, 0, len(rows))
	headerLatencies := make([]float64, 0, len(rows))
	bodyReadTimes := make([]float64, 0, len(rows))
	validationTimes := make([]float64, 0, len(rows))
	successLatencies := make([]float64, 0, len(rows))
	failureLatencies := make([]float64, 0, len(rows))
	serverTimes := make([]float64, 0, len(rows))
	connectionAcquire := make([]float64, 0, len(rows))
	poolWait := make([]float64, 0, len(rows))
	tcpConnect := make([]float64, 0, len(rows))
	firstByte := make([]float64, 0, len(rows))
	responseBytes := make([]int, 0, len(rows))
	statusCounts := map[string]int{}
	protocolCounts := map[string]int{}
	failureCounts := map[string]int{}
	successBySecond := map[string]int{}
	responsesBySecond := map[string]int{}
	failures := make([]failureDetail, 0, failureDetailLimit)
	dispatched, capacityRejected, responseCount, successCount := 0, 0, 0, 0
	timeouts, transportFailures, httpFailures := 0, 0, 0
	candidateTruthMatches, metadataMatches := 0, 0
	payloadContractMatches := 0
	reusedConnections, newConnections := 0, 0
	failureOmitted := 0
	for _, row := range rows {
		if row.CapacityRejected {
			capacityRejected++
			continue
		}
		if !row.Dispatched {
			continue
		}
		dispatched++
		latencies = append(latencies, row.EndToEndMS)
		if row.FullBodyReceivedMS != nil {
			fullBodyReceivedLatencies = append(fullBodyReceivedLatencies, *row.FullBodyReceivedMS)
			if row.Success {
				successfulFullBodyReceivedLatencies = append(successfulFullBodyReceivedLatencies, *row.FullBodyReceivedMS)
			}
		}
		if row.Protocol != "" {
			protocolCounts[row.Protocol]++
		}
		if row.Status > 0 {
			statusCounts[strconv.Itoa(row.Status)]++
		}
		if row.CompletedHTTP {
			responseCount++
			responsesBySecond[strconv.Itoa(int(math.Floor(row.CompletionOffsetS)))]++
		} else if row.Failure == "timeout" {
			timeouts++
		} else {
			transportFailures++
		}
		if row.HeaderLatencyMS != nil {
			headerLatencies = append(headerLatencies, *row.HeaderLatencyMS)
		}
		if row.BodyReadMS != nil {
			bodyReadTimes = append(bodyReadTimes, *row.BodyReadMS)
		}
		if row.ValidationMS != nil {
			validationTimes = append(validationTimes, *row.ValidationMS)
		}
		if row.ServerTimeMS != nil {
			serverTimes = append(serverTimes, *row.ServerTimeMS)
		}
		if row.ConnectionAcquireMS != nil {
			connectionAcquire = append(connectionAcquire, *row.ConnectionAcquireMS)
		}
		if row.EstimatedPoolWaitMS != nil {
			poolWait = append(poolWait, *row.EstimatedPoolWaitMS)
		}
		if row.TCPConnectMS != nil {
			tcpConnect = append(tcpConnect, *row.TCPConnectMS)
		}
		if row.TimeToFirstByteMS != nil {
			firstByte = append(firstByte, *row.TimeToFirstByteMS)
		}
		if row.ResponseBytes > 0 {
			responseBytes = append(responseBytes, row.ResponseBytes)
		}
		if row.CandidateTruthMatch {
			candidateTruthMatches++
		}
		if row.PayloadContractMatch {
			payloadContractMatches++
		}
		if row.MetadataHashMatch {
			metadataMatches++
		}
		if row.ConnectionObserved {
			if row.ConnectionReused {
				reusedConnections++
			} else {
				newConnections++
			}
		}
		if row.Success {
			successCount++
			successLatencies = append(successLatencies, row.EndToEndMS)
			successBySecond[strconv.Itoa(int(math.Floor(row.CompletionOffsetS)))]++
		} else {
			failureLatencies = append(failureLatencies, row.EndToEndMS)
			if row.CompletedHTTP {
				httpFailures++
			}
			failureCounts[row.Failure]++
			if len(failures) < failureDetailLimit {
				failures = append(failures, failureDetail{
					RequestIndex: row.Index, HTTPStatus: row.Status,
					Failure: row.Failure, Rank: row.MismatchRank,
				})
			} else {
				failureOmitted++
			}
		}
	}
	if cfg.mode == "closed-loop" {
		planned = dispatched
	}
	allResponsesRPS := float64(responseCount) / elapsed
	successRPS := float64(successCount) / elapsed
	executableHash, executableHashErr := currentExecutableSHA256()
	mode, shape := cfg.mode, cfg.mode
	offeredRate := cfg.rate
	dispatchWindow := cfg.seconds
	throughputBasis := "completion-based: successful responses divided by monotonic time from run barrier through final full-response validation; elapsed includes drain"
	if cfg.mode == "closed-loop" {
		offeredRate = 0
		throughputBasis = "closed-loop completion-based: each fixed worker dispatches its next request after full response validation; elapsed includes response-body read and validation drain"
	}
	expectedMetadata := make([]string, len(cfg.selected))
	for i, selected := range cfg.selected {
		expectedMetadata[i] = strings.ToLower(selected.MetadataSHA256)
	}
	doc := report{
		Schema: resultSchema, Scope: "HTTP/1.1 B1 transport measurement only; does not measure the full ABIS client or gRPC flow",
		Mode: mode, LoadShape: shape,
		StartedUTC:     started.UTC().Format(time.RFC3339Nano),
		ManifestSHA256: cfg.manifestHash, ManifestPins: cfg.manifestPins,
		ExecutableSHA256: executableHash, ExecutableSHA256Error: executableHashErr,
		Endpoint: cfg.endpoint, RequestProtocol: "HTTP/1.1", GoVersion: runtime.Version(),
		GOMAXPROCS: runtime.GOMAXPROCS(0),
		Transport: transportEvidence{
			HTTP2Disabled: true, ProxyDisabled: true,
			MaxConnsPerHost: cfg.maxInflight, MaxIdleConns: cfg.maxInflight,
			MaxIdleConnsPerHost: cfg.maxInflight, MaxResponseBodyBytes: maxResponseBytes,
			RedirectsFollowed: false, CompressionDisabled: true,
		},
		Concurrency: cfg.concurrency, ConfiguredMaxInflight: cfg.maxInflight,
		OfferedRateHTTPRPS: offeredRate, OfferedDurationS: cfg.seconds,
		DispatchWindowS: dispatchWindow, ActualDispatchDurationS: lastDispatch,
		DrainDurationS: drain, ThroughputBasis: throughputBasis,
		RequestBodyCount: len(cfg.bodies), WarmupRequests: warmupRequests,
		WarmupSuccesses: warmupSuccesses, CandidateTruthCount: cfg.resultLimit,
		ResultLimit: cfg.resultLimit, WithPayload: cfg.withPayload,
		PayloadContract:        payloadContractDescription(cfg.withPayload),
		PayloadContractMatches: payloadContractMatches,
		ExpectedMetadataSHA256: expectedMetadata, ScoreTolerance: cfg.scoreTolerance,
		MaxResponseBodyBytes: maxResponseBytes,
		PlannedRequests:      planned, ClientCapacityRejections: capacityRejected,
		DispatchedRequests: dispatched, HTTPResponses: responseCount,
		SuccessfulRequests: successCount, FailedRequests: dispatched - successCount,
		TransportTimeouts: timeouts, TransportFailures: transportFailures,
		HTTPFailureRequests: httpFailures, ExactCandidateTruth: candidateTruthMatches,
		ExactPayloadContract: payloadContractMatches,
		ExactMetadataHash:    metadataMatches, ActualElapsedS: elapsed,
		SuccessfulCompletedHTTPRPS: successRPS, AllHTTPResponsesPerS: allResponsesRPS,
		PeakInflight: peak, FullClientLatencyMS: summarizeMS(latencies),
		FullBodyReceived:           summarizeMS(fullBodyReceivedLatencies),
		SuccessfulFullBodyReceived: summarizeMS(successfulFullBodyReceivedLatencies),
		HeaderLatencyMS:            summarizeMS(headerLatencies), BodyReadMS: summarizeMS(bodyReadTimes),
		ValidationMS: summarizeMS(validationTimes), SuccessfulLatencyMS: summarizeMS(successLatencies),
		FailureLatencyMS: summarizeMS(failureLatencies), ServerJSONTimeMS: summarizeMS(serverTimes),
		ConnectionAcquireMS: summarizeMS(connectionAcquire), EstimatedPoolWaitMS: summarizeMS(poolWait),
		TCPConnectMS: summarizeMS(tcpConnect), TimeToFirstByteMS: summarizeMS(firstByte),
		ResponseBytes: summarizeBytes(responseBytes), ReusedConnections: reusedConnections,
		NewConnections: newConnections, SuccessfulBySecond: successBySecond,
		HTTPResponsesBySecond: responsesBySecond, HTTPStatusCounts: statusCounts,
		ResponseProtocolCounts: protocolCounts, FailureCounts: failureCounts,
		FailureDetails: failures, FailureDetailsOmitted: failureOmitted,
		HTTPErrorDiagnostics:          cfg.httpErrors.snapshot(),
		QuantileMethod:                "linear interpolation at position (n-1)*p over sorted observations",
		MetadataHashMethod:            metadataHashDescription(cfg.withPayload),
		APIKeyHandling:                "read from configured environment variable; never included in output",
		RawRequestsOrPayloadsIncluded: false,
	}
	if warmupRequests > 0 {
		doc.ThroughputBasis += fmt.Sprintf("; %d unmeasured warmup requests succeeded before the barrier", warmupSuccesses)
	}
	return doc, nil
}

func summarizeMS(values []float64) latencySummary {
	if len(values) == 0 {
		return latencySummary{}
	}
	sorted := append([]float64(nil), values...)
	sort.Float64s(sorted)
	mean := 0.0
	for _, value := range sorted {
		mean += value
	}
	mean /= float64(len(sorted))
	max := sorted[len(sorted)-1]
	return latencySummary{
		Count: len(sorted), P50MS: quantile(sorted, 0.50), P95MS: quantile(sorted, 0.95),
		P99MS: quantile(sorted, 0.99), MeanMS: &mean, MaxMS: &max,
	}
}

func summarizeBytes(values []int) byteSummary {
	if len(values) == 0 {
		return byteSummary{}
	}
	total, minValue, maxValue := 0, values[0], values[0]
	for _, value := range values {
		total += value
		if value < minValue {
			minValue = value
		}
		if value > maxValue {
			maxValue = value
		}
	}
	return byteSummary{Count: len(values), Min: minValue, Mean: float64(total) / float64(len(values)), Max: maxValue}
}

func quantile(sorted []float64, probability float64) *float64 {
	if len(sorted) == 0 {
		return nil
	}
	position := float64(len(sorted)-1) * probability
	lower := int(position)
	upper := min(lower+1, len(sorted)-1)
	value := sorted[lower] + (sorted[upper]-sorted[lower])*(position-float64(lower))
	return &value
}

func durationMS(value time.Duration) float64 { return float64(value) / float64(time.Millisecond) }

func intPointer(value int) *int { return &value }

func writeOutput(path string, encoded []byte) error {
	if path == "" {
		_, err := os.Stdout.Write(encoded)
		return err
	}
	return os.WriteFile(path, encoded, 0o600)
}

func currentExecutableSHA256() (string, string) {
	executable, err := os.Executable()
	if err != nil {
		return "", err.Error()
	}
	file, err := os.Open(executable)
	if err != nil {
		return "", err.Error()
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err.Error()
	}
	return hex.EncodeToString(hash.Sum(nil)), ""
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(2)
}
