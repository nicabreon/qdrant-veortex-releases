// Command bench-matrix runs the shared closed-loop B1/B4/B16/B32/B64 client
// against a Qdrant-compatible /points/search endpoint using frozen B1 manifests.
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
	"net/http"
	"net/http/httptrace"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

const (
	manifestSchema       = "benchmark_abis_payload_b1_top10_go_manifest_v1"
	resultSchema         = "qdrant_search_batch_matrix_http_v1"
	queryCount           = 1024
	resultLimit          = 10
	maxResponseBodyBytes = 8 << 20
	maxInflight          = 160
	failureDetailLimit   = 50
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

type selectedTruth struct {
	MetadataSHA256 string `json:"metadata_sha256"`
}

type typedTruthHit struct {
	ID    int64
	Score float64
}

type expectedABIS struct {
	Active               bool   `json:"active"`
	BiometricRecordID    string `json:"biometric_record_id"`
	CollectionID         string `json:"collection_id"`
	ModelVersion         string `json:"model_version"`
	NormalizationVersion string `json:"normalization_version"`
	Operation            string `json:"operation"`
	SubjectID            string `json:"subject_id"`
}

type expectedAttributes struct {
	Position string `json:"position"`
	Status   string `json:"status"`
}

type expectedPayload struct {
	ABIS       expectedABIS       `json:"abis"`
	Attributes expectedAttributes `json:"attributes"`
}

type returnedPayload struct {
	ABIS       *returnedABIS       `json:"abis"`
	Attributes *returnedAttributes `json:"attributes"`
}

type returnedABIS struct {
	Active               *bool   `json:"active"`
	BiometricRecordID    *string `json:"biometric_record_id"`
	CollectionID         *string `json:"collection_id"`
	ModelVersion         *string `json:"model_version"`
	NormalizationVersion *string `json:"normalization_version"`
	Operation            *string `json:"operation"`
	SubjectID            *string `json:"subject_id"`
}

type returnedAttributes struct {
	Position *string `json:"position"`
	Status   *string `json:"status"`
}

type metadataRow struct {
	ID      int64           `json:"id"`
	Payload expectedPayload `json:"payload"`
}

type responseHit struct {
	ID       json.RawMessage `json:"id"`
	Version  json.RawMessage `json:"version,omitempty"`
	Score    json.RawMessage `json:"score"`
	Payload  json.RawMessage `json:"payload,omitempty"`
	ShardKey json.RawMessage `json:"shard_key,omitempty"`
}

type responseEnvelope struct {
	Result json.RawMessage `json:"result"`
	Status json.RawMessage `json:"status"`
	Time   json.RawMessage `json:"time"`
}

type config struct {
	manifestHash string
	endpoint     string
	bodies       [][]byte
	truth        [][]typedTruthHit
	selected     []selectedTruth
	withPayload  bool
	batchSize    int
	concurrency  int
	maxInflight  int
	seconds      float64
	timeout      time.Duration
	warmup       int
	tolerance    float64
	apiKey       string
}

type sample struct {
	RequestIndex int     `json:"request_index"`
	Status       int     `json:"http_status,omitempty"`
	Protocol     string  `json:"protocol,omitempty"`
	Failure      string  `json:"failure,omitempty"`
	QueryStart   int     `json:"query_start_index"`
	Queries      int     `json:"queries_in_request"`
	LatencyMS    float64 `json:"full_response_validated_latency_ms"`
	DispatchedS  float64 `json:"dispatch_offset_s"`
	CompletedS   float64 `json:"completion_offset_s"`
	ServerTimeMS float64 `json:"server_json_time_ms,omitempty"`
	AcquireMS    float64 `json:"connection_acquire_ms,omitempty"`
	TruthMatches int     `json:"exact_query_truth_matches"`
	ValidQueries int     `json:"successful_queries"`
	PayloadHits  int     `json:"payload_contract_matches"`
	HTTPResponse bool    `json:"-"`
	Success      bool    `json:"-"`
	ServerTimeOK bool    `json:"-"`
	AcquireOK    bool    `json:"-"`
}

type failureDetail struct {
	RequestIndex int    `json:"request_index"`
	HTTPStatus   int    `json:"http_status,omitempty"`
	Failure      string `json:"failure"`
	QueryStart   int    `json:"query_start_index"`
}

type latencyStats struct {
	Count  int      `json:"count"`
	P50MS  *float64 `json:"p50_ms"`
	P95MS  *float64 `json:"p95_ms"`
	P99MS  *float64 `json:"p99_ms"`
	MeanMS *float64 `json:"mean_ms"`
	MaxMS  *float64 `json:"max_ms"`
}

type report struct {
	Schema                  string          `json:"schema"`
	Status                  string          `json:"status"`
	Passed                  bool            `json:"passed"`
	StartedUTC              string          `json:"started_utc"`
	FinishedUTC             string          `json:"finished_utc"`
	ManifestSHA256          string          `json:"manifest_sha256"`
	ExecutableSHA256        string          `json:"executable_sha256,omitempty"`
	ExecutableSHA256Error   string          `json:"executable_sha256_error,omitempty"`
	Endpoint                string          `json:"endpoint"`
	RequestProtocol         string          `json:"request_protocol"`
	BatchSize               int             `json:"batch_size"`
	Concurrency             int             `json:"concurrency"`
	MaxInflight             int             `json:"max_inflight"`
	GOMAXPROCS              int             `json:"gomaxprocs"`
	DispatchWindowS         float64         `json:"dispatch_window_s"`
	ActualDispatchS         float64         `json:"actual_dispatch_duration_s"`
	DrainS                  float64         `json:"drain_duration_s"`
	ActualElapsedS          float64         `json:"actual_elapsed_s"`
	ThroughputBasis         string          `json:"throughput_basis"`
	WarmupRequests          int             `json:"warmup_requests"`
	WarmupConfigured        int             `json:"warmup_configured_requests"`
	WarmupSuccesses         int             `json:"warmup_successes"`
	WarmupFailedRequests    int             `json:"warmup_failed_requests"`
	WarmupQueries           int             `json:"warmup_queries"`
	WarmupSuccessfulQueries int             `json:"warmup_successful_queries"`
	WarmupFailedQueries     int             `json:"warmup_failed_queries"`
	WarmupExactTruthMatches int             `json:"warmup_exact_query_truth_matches"`
	WarmupPayloadMatches    int             `json:"warmup_payload_contract_matches"`
	ResultLimit             int             `json:"result_limit"`
	WithPayload             bool            `json:"with_payload"`
	ScoreTolerance          float64         `json:"score_tolerance"`
	MaxResponseBodyBytes    int             `json:"max_response_body_bytes"`
	PlannedRequests         int             `json:"planned_requests"`
	DispatchedRequests      int             `json:"dispatched_requests"`
	DispatchedQueries       int             `json:"dispatched_queries"`
	HTTPResponses           int             `json:"http_responses"`
	WarmupHTTPResponses     int             `json:"warmup_http_responses"`
	SuccessfulRequests      int             `json:"successful_requests"`
	FailedRequests          int             `json:"failed_requests"`
	SuccessfulQueries       int             `json:"successful_queries"`
	FailedQueries           int             `json:"failed_queries"`
	ExactQueryTruthMatches  int             `json:"exact_query_truth_matches"`
	PayloadContractMatches  int             `json:"payload_contract_matches"`
	HTTP429Count            int             `json:"http_429_count"`
	WarmupHTTP429Count      int             `json:"warmup_http_429_count"`
	HTTPErrorRequests       int             `json:"http_error_requests"`
	WarmupHTTPErrorRequests int             `json:"warmup_http_error_requests"`
	TransportFailures       int             `json:"transport_failures"`
	TransportTimeouts       int             `json:"transport_timeouts"`
	ProtocolErrors          int             `json:"protocol_errors"`
	CorrectnessFailed       int             `json:"correctness_failed_requests"`
	PeakInflight            int             `json:"peak_inflight"`
	SuccessfulHTTPRPS       float64         `json:"successful_http_rps"`
	QueryQPS                float64         `json:"query_qps"`
	HTTPStatusCounts        map[string]int  `json:"http_status_counts"`
	ProtocolCounts          map[string]int  `json:"response_protocol_counts"`
	FailureCounts           map[string]int  `json:"failure_counts"`
	Latency                 latencyStats    `json:"full_response_validated_latency_ms"`
	ServerTime              latencyStats    `json:"server_json_time_ms"`
	ConnectionAcquire       latencyStats    `json:"connection_acquire_ms"`
	Failures                []failureDetail `json:"failure_details"`
	FailureDetailsOmitted   int             `json:"failure_details_omitted"`
	APIKeyHandling          string          `json:"api_key_handling"`
	CredentialsIncluded     bool            `json:"credentials_included_in_report"`
}

func main() {
	manifestPath := flag.String("manifest", "", "frozen B1 Top10 manifest JSON (required)")
	outputPath := flag.String("output", "", "write JSON report to this path (default stdout)")
	validateOnly := flag.Bool("validate-manifest-only", false, "validate manifest offline without reading the API key or making requests")
	mode := flag.String("mode", "closed-loop", "closed-loop only")
	concurrency := flag.Int("concurrency", 1, "closed-loop worker count (1..160)")
	maxIn := flag.Int("max-inflight", 0, "maximum in-flight requests (defaults to concurrency; 1..160)")
	batch := flag.Int("batch-size", 1, "searches per HTTP request: 1, 4, 16, 32, or 64")
	seconds := flag.Float64("seconds", 60, "measured dispatch window in seconds")
	gomax := flag.Int("gomaxprocs", 7, "Go scheduler parallelism")
	warmup := flag.Int("warmup-requests", 16, "successful full-response requests excluded from timing")
	timeout := flag.Duration("timeout", 60*time.Second, "per-request timeout including response body read")
	tolerance := flag.Float64("score-tolerance", 1e-6, "maximum absolute candidate score difference")
	flag.Parse()

	if *manifestPath == "" {
		fatalf("--manifest is required")
	}
	loaded, hash, bodies, truth, selected, err := loadManifest(*manifestPath)
	if err != nil {
		fatalf("manifest: %v", err)
	}
	if *validateOnly {
		writeValidation(*outputPath, hash, *loaded.WithPayload)
		return
	}
	if *mode != "closed-loop" {
		fatalf("--mode must be closed-loop")
	}
	if !validBatch(*batch) {
		fatalf("--batch-size must be one of 1, 4, 16, 32, or 64")
	}
	if *concurrency < 1 || *concurrency > maxInflight {
		fatalf("--concurrency must be in 1..%d", maxInflight)
	}
	if *maxIn == 0 {
		*maxIn = *concurrency
	}
	if *maxIn < *concurrency || *maxIn > maxInflight {
		fatalf("--max-inflight must be >= --concurrency and <= %d", maxInflight)
	}
	if *seconds <= 0 || math.IsNaN(*seconds) || math.IsInf(*seconds, 0) {
		fatalf("--seconds must be finite and positive")
	}
	if *gomax < 1 || *gomax > 128 || *warmup < 0 || *warmup > 256 || *timeout <= 0 || *tolerance < 0 || math.IsNaN(*tolerance) || math.IsInf(*tolerance, 0) {
		fatalf("invalid gomaxprocs, warmup, timeout, or score tolerance")
	}
	endpoint, err := workloadEndpoint(loaded.Endpoint, *batch)
	if err != nil {
		fatalf("endpoint: %v", err)
	}
	apiKey := os.Getenv("QDRANT_API_KEY")
	if apiKey == "" {
		fatalf("QDRANT_API_KEY is empty or unset")
	}
	runtime.GOMAXPROCS(*gomax)
	cfg := config{manifestHash: hash, endpoint: endpoint, bodies: bodies, truth: truth, selected: selected,
		withPayload: *loaded.WithPayload, batchSize: *batch, concurrency: *concurrency, maxInflight: *maxIn,
		seconds: *seconds, timeout: *timeout, warmup: *warmup, tolerance: *tolerance, apiKey: apiKey}
	client, transport := newHTTPClient(cfg.maxInflight)
	defer transport.CloseIdleConnections()
	startUTC := time.Now().UTC()
	started := time.Now()
	doc := newReport(cfg, startUTC, cfg.endpoint)
	var warmedRequests int64

	for i := 0; i < cfg.warmup; i++ {
		start := i * cfg.batchSize
		row := execute(client, cfg, i, start, started)
		doc.WarmupRequests++
		doc.WarmupQueries += cfg.batchSize
		doc.WarmupSuccessfulQueries += row.ValidQueries
		countRow(&doc, row, true)
		if !row.Success {
			doc.WarmupFailedRequests = 1
			doc.WarmupFailedQueries = cfg.batchSize - row.ValidQueries
			appendFailure(&doc, row)
			doc.Status = "WARMUP_FAILED"
			doc.WarmupConfigured = cfg.warmup
			finishReport(&doc, time.Now(), cfg)
			if err := writeReport(*outputPath, doc); err != nil {
				fatalf("write failed warmup report: %v", err)
			}
			os.Exit(1)
		}
		doc.WarmupSuccesses++
		warmedRequests++
	}
	// Warm-up successes are retained as their own counts and omitted from the
	// timed-row latency/RPS aggregates. A timing barrier starts only after warmup.
	measureStart := time.Now()
	rows, actualDispatch, drain, peak := runClosedLoop(client, cfg, warmedRequests, measureStart)
	doc.ActualDispatchS = actualDispatch
	doc.DrainS = drain
	doc.ActualElapsedS = actualDispatch + drain
	doc.PeakInflight = peak
	var latencies, serverTimes, acquireTimes []float64
	for _, row := range rows {
		countRow(&doc, row, false)
		latencies = append(latencies, row.LatencyMS)
		if row.ServerTimeOK {
			serverTimes = append(serverTimes, row.ServerTimeMS)
		}
		if row.AcquireOK {
			acquireTimes = append(acquireTimes, row.AcquireMS)
		}
		if !row.Success {
			appendFailure(&doc, row)
		}
	}
	doc.Latency = summarizeLatencies(latencies)
	doc.ServerTime = summarizeLatencies(serverTimes)
	doc.ConnectionAcquire = summarizeLatencies(acquireTimes)
	doc.PlannedRequests = doc.DispatchedRequests
	if doc.ActualElapsedS > 0 {
		doc.SuccessfulHTTPRPS = float64(doc.SuccessfulRequests) / doc.ActualElapsedS
		doc.QueryQPS = float64(doc.SuccessfulRequests*cfg.batchSize) / doc.ActualElapsedS
	}
	doc.FailedQueries = doc.DispatchedQueries - doc.SuccessfulQueries
	if doc.FailedRequests == 0 && doc.WarmupFailedRequests == 0 {
		doc.Status = "COMPLETED"
	} else {
		doc.Status = "COMPLETED_WITH_FAILURES"
	}
	doc.WarmupConfigured = cfg.warmup
	finishReport(&doc, time.Now(), cfg)
	if err := writeReport(*outputPath, doc); err != nil {
		fatalf("write report: %v", err)
	}
	if doc.FailedRequests > 0 || doc.WarmupFailedRequests > 0 {
		os.Exit(1)
	}
}

func validBatch(b int) bool { return b == 1 || b == 4 || b == 16 || b == 32 || b == 64 }

func newReport(cfg config, started time.Time, requestEndpoint string) report {
	return report{Schema: resultSchema, Status: "RUNNING", StartedUTC: started.Format(time.RFC3339Nano),
		ManifestSHA256: cfg.manifestHash, Endpoint: requestEndpoint, RequestProtocol: "HTTP/1.1",
		BatchSize: cfg.batchSize, Concurrency: cfg.concurrency, MaxInflight: cfg.maxInflight,
		GOMAXPROCS: runtime.GOMAXPROCS(0), DispatchWindowS: cfg.seconds,
		WarmupConfigured: cfg.warmup, ResultLimit: resultLimit, WithPayload: cfg.withPayload,
		ScoreTolerance: cfg.tolerance, MaxResponseBodyBytes: maxResponseBodyBytes,
		HTTPStatusCounts: map[string]int{}, ProtocolCounts: map[string]int{}, FailureCounts: map[string]int{},
		APIKeyHandling: "read only from QDRANT_API_KEY; never included in output", CredentialsIncluded: false}
}

func loadManifest(path string) (manifest, string, [][]byte, [][]typedTruthHit, []selectedTruth, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	h := sha256.Sum256(raw)
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	var m manifest
	if err := decoder.Decode(&m); err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return manifest{}, "", nil, nil, nil, errors.New("manifest has trailing JSON")
	}
	if m.Schema != manifestSchema || m.QueryCount != queryCount || m.ResultLimit != resultLimit || m.WithPayload == nil {
		return manifest{}, "", nil, nil, nil, errors.New("manifest must match the legacy 1,024-query Top10 B1 schema")
	}
	if len(m.RequestBodiesBase64) != queryCount || len(m.CandidateTruth) != queryCount || len(m.ExpectedSelected) != queryCount {
		return manifest{}, "", nil, nil, nil, errors.New("manifest arrays must each contain exactly 1,024 rows")
	}
	if len(m.Pins) == 0 || !json.Valid(m.Pins) {
		return manifest{}, "", nil, nil, nil, errors.New("manifest pins must be valid JSON")
	}
	bodies := make([][]byte, queryCount)
	truth := make([][]typedTruthHit, queryCount)
	filterMode := ""
	for i, encoded := range m.RequestBodiesBase64 {
		body, err := base64.StdEncoding.DecodeString(encoded)
		if err != nil || !json.Valid(body) {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("request body %d is invalid base64 or JSON", i)
		}
		if err := validateRequestBody(body, *m.WithPayload); err != nil {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("request body %d: %w", i, err)
		}
		mode, err := bodyFilterMode(body)
		if err != nil || (filterMode != "" && filterMode != mode) {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("request body %d has inconsistent or unsupported filter", i)
		}
		filterMode = mode
		bodies[i] = body
		if len(m.CandidateTruth[i]) != resultLimit {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("candidate_truth[%d] must contain Top10", i)
		}
		truth[i] = make([]typedTruthHit, resultLimit)
		seen := make(map[int64]bool, resultLimit)
		for rank, hit := range m.CandidateTruth[i] {
			var id int64
			if err := json.Unmarshal(hit.ID, &id); err != nil || id < 0 || id >= 3_000_000 || seen[id] {
				return manifest{}, "", nil, nil, nil, fmt.Errorf("candidate_truth[%d][%d] has invalid or repeated numeric ID", i, rank)
			}
			var score float64
			if err := json.Unmarshal(hit.Score, &score); err != nil || !finite(score) {
				return manifest{}, "", nil, nil, nil, fmt.Errorf("candidate_truth[%d][%d] has non-finite score", i, rank)
			}
			seen[id] = true
			truth[i][rank] = typedTruthHit{ID: id, Score: score}
		}
		if !validSHA256(m.ExpectedSelected[i].MetadataSHA256) {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("expected_selected[%d] is not a SHA-256 digest", i)
		}
		derived := expectedMetadataSHA256(truth[i])
		if !strings.EqualFold(derived, m.ExpectedSelected[i].MetadataSHA256) {
			return manifest{}, "", nil, nil, nil, fmt.Errorf("expected_selected[%d] disagrees with candidate IDs and deterministic payload schema", i)
		}
	}
	var pins map[string]json.RawMessage
	if err := json.Unmarshal(m.Pins, &pins); err != nil || pins == nil {
		return manifest{}, "", nil, nil, nil, errors.New("manifest pins must be an object")
	}
	var pinnedQueryCount, pinnedLimit int
	var pinnedPayload bool
	if json.Unmarshal(pins["query_count"], &pinnedQueryCount) != nil || pinnedQueryCount != queryCount ||
		json.Unmarshal(pins["result_limit"], &pinnedLimit) != nil || pinnedLimit != resultLimit ||
		json.Unmarshal(pins["with_payload"], &pinnedPayload) != nil || pinnedPayload != *m.WithPayload {
		return manifest{}, "", nil, nil, nil, errors.New("manifest pins disagree with query count, Top10, or payload mode")
	}
	pinnedFilter, ok := pins["filter"]
	if !ok {
		return manifest{}, "", nil, nil, nil, errors.New("manifest pins.filter is required")
	}
	filterBody, _ := json.Marshal(map[string]json.RawMessage{"filter": pinnedFilter})
	pinnedMode, err := bodyFilterMode(filterBody)
	if err != nil || pinnedMode != filterMode {
		return manifest{}, "", nil, nil, nil, errors.New("manifest pins.filter disagrees with request bodies")
	}
	if err := validateEndpoint(m.Endpoint); err != nil {
		return manifest{}, "", nil, nil, nil, err
	}
	return m, hex.EncodeToString(h[:]), bodies, truth, m.ExpectedSelected, nil
}

func validateRequestBody(body []byte, withPayload bool) error {
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(body, &fields); err != nil || fields == nil {
		return errors.New("body must be a JSON object")
	}
	var limit int
	if json.Unmarshal(fields["limit"], &limit) != nil || limit != resultLimit {
		return errors.New("limit must be 10")
	}
	var wp bool
	if json.Unmarshal(fields["with_payload"], &wp) != nil || wp != withPayload {
		return errors.New("with_payload does not match manifest")
	}
	var withVector bool
	if json.Unmarshal(fields["with_vector"], &withVector) != nil || withVector {
		return errors.New("with_vector must be false")
	}
	var vector struct {
		Name   string    `json:"name"`
		Vector []float64 `json:"vector"`
	}
	if json.Unmarshal(fields["vector"], &vector) != nil || vector.Name == "" || len(vector.Vector) != 512 {
		return errors.New("vector must be a named 512-dimensional vector")
	}
	for _, v := range vector.Vector {
		if !finite(v) {
			return errors.New("vector contains a non-finite value")
		}
	}
	var params struct {
		Exact        *bool `json:"exact"`
		Quantization struct {
			Rescore *bool `json:"rescore"`
			Ignore  *bool `json:"ignore"`
		} `json:"quantization"`
	}
	if json.Unmarshal(fields["params"], &params) != nil || params.Exact == nil || *params.Exact || params.Quantization.Rescore == nil || !*params.Quantization.Rescore || params.Quantization.Ignore == nil || *params.Quantization.Ignore {
		return errors.New("params must use approximate quantized search with rescore=true and ignore=false")
	}
	return nil
}

func bodyFilterMode(body []byte) (string, error) {
	var v struct {
		Filter json.RawMessage `json:"filter"`
	}
	if err := json.Unmarshal(body, &v); err != nil {
		return "", err
	}
	if len(v.Filter) == 0 || string(v.Filter) == "null" {
		return "unfiltered", nil
	}
	var f struct {
		Must []struct {
			Key   string `json:"key"`
			Match struct {
				Value json.RawMessage `json:"value"`
			} `json:"match"`
		} `json:"must"`
		MustNot []struct {
			Key   string `json:"key"`
			Match struct {
				Value string `json:"value"`
			} `json:"match"`
		} `json:"must_not"`
	}
	if json.Unmarshal(v.Filter, &f) != nil || len(f.Must) < 1 || len(f.Must) > 2 {
		return "", errors.New("unsupported filter shape")
	}
	active, position := false, false
	for _, clause := range f.Must {
		switch clause.Key {
		case "abis.active":
			active = string(clause.Match.Value) == "true"
		case "attributes.position":
			var v string
			if json.Unmarshal(clause.Match.Value, &v) != nil || v != "left_index" {
				return "", errors.New("position filter must match left_index")
			}
			position = true
		default:
			return "", errors.New("unsupported filter key")
		}
	}
	if !active {
		return "", errors.New("filter must contain abis.active=true")
	}
	if position {
		if len(f.MustNot) != 1 || f.MustNot[0].Key != "abis.subject_id" || f.MustNot[0].Match.Value != "00000000-0000-4000-8000-000000000001" {
			return "", errors.New("position filter must exclude the benchmark subject")
		}
		return "active_position_exclude", nil
	}
	if len(f.MustNot) != 0 {
		return "", errors.New("active-only filter must not include must_not")
	}
	return "active_only", nil
}

func validateEndpoint(value string) error {
	u, err := url.Parse(value)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" || u.User != nil || u.Fragment != "" {
		return errors.New("endpoint must be an absolute HTTP(S) URL without userinfo or fragment")
	}
	if !strings.HasSuffix(u.Path, "/points/search") {
		return errors.New("manifest endpoint must end in /points/search")
	}
	if q := u.Query(); len(q) != 1 || len(q["consistency"]) != 1 || q.Get("consistency") != "quorum" {
		return errors.New("only consistency=quorum is allowed in the endpoint query")
	}
	return nil
}

func workloadEndpoint(base string, batch int) (string, error) {
	u, err := url.Parse(base)
	if err != nil {
		return "", err
	}
	if batch > 1 {
		u.Path = strings.TrimSuffix(u.Path, "/search") + "/search/batch"
	}
	return u.String(), nil
}

func expectedPayloadForID(id int64) expectedPayload {
	active := (id/10)%10 != 0
	status := "inactive"
	if active {
		status = "active"
	}
	positions := [...]string{"left_thumb", "left_index", "left_middle", "left_ring", "left_little", "right_thumb", "right_index", "right_middle", "right_ring", "right_little"}
	return expectedPayload{ABIS: expectedABIS{Active: active,
		BiometricRecordID: fmt.Sprintf("00000001-0000-4000-8000-%012x", id),
		CollectionID:      "00000002-0000-4000-8000-000000000001", ModelVersion: "gaussian-512-bench-v1",
		NormalizationVersion: "cosine-l2-f32-v1", Operation: "upsert",
		SubjectID: fmt.Sprintf("00000000-0000-4000-8000-%012x", id/10)},
		Attributes: expectedAttributes{Position: positions[id%10], Status: status}}
}

func expectedMetadataSHA256(truth []typedTruthHit) string {
	rows := make([]metadataRow, len(truth))
	for i, hit := range truth {
		rows[i] = metadataRow{ID: hit.ID, Payload: expectedPayloadForID(hit.ID)}
	}
	b, _ := json.Marshal(rows)
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}

func validSHA256(s string) bool {
	if len(s) != sha256.Size*2 {
		return false
	}
	_, err := hex.DecodeString(s)
	return err == nil
}

func finite(f float64) bool { return !math.IsNaN(f) && !math.IsInf(f, 0) }

func writeValidation(path, hash string, withPayload bool) {
	doc := map[string]any{"schema": "qdrant_search_batch_manifest_validation_v1", "status": "VALIDATED",
		"manifest_sha256": hash, "query_count": queryCount, "result_limit": resultLimit, "with_payload": withPayload}
	b, _ := json.MarshalIndent(doc, "", "  ")
	if err := writeOutput(path, append(b, '\n')); err != nil {
		fatalf("write validation report: %v", err)
	}
}

func newHTTPClient(conns int) (*http.Client, *http.Transport) {
	tr := &http.Transport{Proxy: nil, MaxConnsPerHost: conns, MaxIdleConns: conns,
		MaxIdleConnsPerHost: conns, IdleConnTimeout: 60 * time.Second, TLSHandshakeTimeout: 10 * time.Second,
		ExpectContinueTimeout: time.Second, ForceAttemptHTTP2: false,
		TLSNextProto: map[string]func(string, *tls.Conn) http.RoundTripper{}, DisableCompression: true}
	c := &http.Client{Transport: tr, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	return c, tr
}

func runClosedLoop(client *http.Client, cfg config, firstRequest int64, barrier time.Time) ([]sample, float64, float64, int) {
	ready := sync.WaitGroup{}
	ready.Add(cfg.concurrency)
	gate := make(chan struct{})
	var deadline time.Time
	var workers sync.WaitGroup
	var nextRequest atomic.Int64
	var nextQuery atomic.Int64
	var active atomic.Int64
	var peak atomic.Int64
	nextRequest.Store(firstRequest)
	nextQuery.Store(firstRequest * int64(cfg.batchSize))
	perWorker := make([][]sample, cfg.concurrency)
	for worker := 0; worker < cfg.concurrency; worker++ {
		workers.Add(1)
		go func(index int) {
			defer workers.Done()
			ready.Done()
			<-gate
			for time.Now().Before(deadline) {
				reqIndex := int(nextRequest.Add(1) - 1)
				queryStart := int(nextQuery.Add(int64(cfg.batchSize)) - int64(cfg.batchSize))
				activeNow := active.Add(1)
				for old := peak.Load(); activeNow > old && !peak.CompareAndSwap(old, activeNow); old = peak.Load() {
				}
				r := execute(client, cfg, reqIndex, queryStart, barrier)
				active.Add(-1)
				perWorker[index] = append(perWorker[index], r)
			}
		}(worker)
	}
	ready.Wait()
	barrier = time.Now()
	deadline = barrier.Add(time.Duration(cfg.seconds * float64(time.Second)))
	close(gate)
	workers.Wait()
	rows := make([]sample, 0)
	var lastDispatch, lastComplete float64
	for _, workerRows := range perWorker {
		rows = append(rows, workerRows...)
		for _, row := range workerRows {
			if row.DispatchedS > lastDispatch {
				lastDispatch = row.DispatchedS
			}
			if row.CompletedS > lastComplete {
				lastComplete = row.CompletedS
			}
		}
	}
	if lastComplete < lastDispatch {
		lastComplete = lastDispatch
	}
	return rows, lastDispatch, math.Max(0, lastComplete-lastDispatch), int(peak.Load())
}

func execute(client *http.Client, cfg config, requestIndex, queryStart int, barrier time.Time) sample {
	dispatched := time.Now()
	row := sample{RequestIndex: requestIndex, QueryStart: queryStart % queryCount, Queries: cfg.batchSize,
		DispatchedS: dispatched.Sub(barrier).Seconds()}
	queries := make([]int, cfg.batchSize)
	var body []byte
	if cfg.batchSize == 1 {
		queries[0] = queryStart % queryCount
		body = cfg.bodies[queries[0]]
	} else {
		var b bytes.Buffer
		b.WriteString(`{"searches":[`)
		for i := 0; i < cfg.batchSize; i++ {
			if i != 0 {
				b.WriteByte(',')
			}
			qi := (queryStart + i) % queryCount
			queries[i] = qi
			b.Write(cfg.bodies[qi])
		}
		b.WriteString(`]}`)
		body = b.Bytes()
	}
	ctx, cancel := context.WithTimeout(context.Background(), cfg.timeout)
	defer cancel()
	trace := &connectionTrace{}
	ctx = httptrace.WithClientTrace(ctx, trace.clientTrace(dispatched))
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, cfg.endpoint, bytes.NewReader(body))
	if err != nil {
		row.Failure = "request_build_error"
		return finishSample(row, dispatched, barrier)
	}
	req.Header.Set("api-key", cfg.apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		row.Failure = "transport_error"
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(ctx.Err(), context.DeadlineExceeded) {
			row.Failure = "timeout"
		}
		return finishSample(row, dispatched, barrier)
	}
	row.Status = resp.StatusCode
	row.Protocol = resp.Proto
	row.HTTPResponse = true
	row.AcquireMS, row.AcquireOK = trace.acquisitionMS(dispatched)
	respBody, readErr := io.ReadAll(io.LimitReader(resp.Body, maxResponseBodyBytes+1))
	closeErr := resp.Body.Close()
	if readErr != nil {
		row.Failure = "response_read_error"
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			row.Failure = "timeout"
		}
		return finishSample(row, dispatched, barrier)
	}
	if closeErr != nil {
		row.Failure = "response_close_error"
		return finishSample(row, dispatched, barrier)
	}
	if len(respBody) > maxResponseBodyBytes {
		row.Failure = "response_too_large"
		return finishSample(row, dispatched, barrier)
	}
	if resp.StatusCode != http.StatusOK {
		row.Failure = "http_status_" + strconv.Itoa(resp.StatusCode)
		return finishSample(row, dispatched, barrier)
	}
	if resp.Proto != "HTTP/1.1" {
		row.Failure = "protocol_not_http_1_1"
		return finishSample(row, dispatched, barrier)
	}
	var envelope responseEnvelope
	if err := json.Unmarshal(respBody, &envelope); err != nil {
		row.Failure = "invalid_response_json"
		return finishSample(row, dispatched, barrier)
	}
	var status string
	if json.Unmarshal(envelope.Status, &status) != nil || status != "ok" {
		row.Failure = "invalid_response_status"
		return finishSample(row, dispatched, barrier)
	}
	var serverTime float64
	if json.Unmarshal(envelope.Time, &serverTime) != nil || !finite(serverTime) || serverTime < 0 {
		row.Failure = "invalid_server_time"
		return finishSample(row, dispatched, barrier)
	}
	row.ServerTimeMS = serverTime * 1000
	row.ServerTimeOK = true
	resultSets, err := decodeResultSets(envelope.Result, cfg.batchSize)
	if err != nil {
		row.Failure = "invalid_batch_result_shape"
		return finishSample(row, dispatched, barrier)
	}
	for i := 0; i < len(resultSets) && i < cfg.batchSize; i++ {
		truthOK, payloadOK, why := validateQueryHits(resultSets[i], cfg.truth[queries[i]], cfg.withPayload, cfg.tolerance)
		if truthOK {
			row.TruthMatches++
		}
		if payloadOK {
			row.PayloadHits++
		}
		if truthOK && payloadOK {
			row.ValidQueries++
		}
		if why != "" && row.Failure == "" {
			row.Failure = why
		}
	}
	if len(resultSets) != cfg.batchSize && row.Failure == "" {
		row.Failure = "batch_result_count_mismatch"
	}
	if row.Failure == "" && row.ValidQueries == cfg.batchSize {
		row.Success = true
	}
	if row.Failure == "" && !row.Success {
		row.Failure = "query_validation_failed"
	}
	return finishSample(row, dispatched, barrier)
}

type connectionTrace struct {
	mu  sync.Mutex
	get time.Time
	got time.Time
}

func (t *connectionTrace) clientTrace(dispatched time.Time) *httptrace.ClientTrace {
	return &httptrace.ClientTrace{GetConn: func(string) { t.mu.Lock(); t.get = time.Now(); t.mu.Unlock() },
		GotConn: func(httptrace.GotConnInfo) { t.mu.Lock(); t.got = time.Now(); t.mu.Unlock() }}
}

func (t *connectionTrace) acquisitionMS(dispatched time.Time) (float64, bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if !t.got.IsZero() {
		start := t.get
		if start.IsZero() {
			start = dispatched
		}
		return t.got.Sub(start).Seconds() * 1000, true
	}
	return 0, false
}

func decodeResultSets(raw json.RawMessage, batch int) ([][]json.RawMessage, error) {
	var outer []json.RawMessage
	if err := json.Unmarshal(raw, &outer); err != nil {
		return nil, err
	}
	if batch == 1 {
		if len(outer) > 0 && bytes.HasPrefix(bytes.TrimSpace(outer[0]), []byte("[")) {
			if len(outer) != 1 {
				return nil, errors.New("unexpected nested B1 result")
			}
			var hits []json.RawMessage
			if err := json.Unmarshal(outer[0], &hits); err != nil {
				return nil, err
			}
			return [][]json.RawMessage{hits}, nil
		}
		return [][]json.RawMessage{outer}, nil
	}
	sets := make([][]json.RawMessage, len(outer))
	for i, rawSet := range outer {
		if err := json.Unmarshal(rawSet, &sets[i]); err != nil {
			return nil, fmt.Errorf("result[%d] is not a hit array", i)
		}
	}
	return sets, nil
}

func validateQueryHits(rawHits []json.RawMessage, truth []typedTruthHit, withPayload bool, tolerance float64) (bool, bool, string) {
	if len(rawHits) != resultLimit || len(truth) != resultLimit {
		return false, false, "candidate_count_mismatch"
	}
	truthOK, payloadOK := true, true
	for rank, raw := range rawHits {
		var hit responseHit
		dec := json.NewDecoder(bytes.NewReader(raw))
		dec.DisallowUnknownFields()
		if dec.Decode(&hit) != nil {
			return false, false, "invalid_hit_shape"
		}
		var id int64
		var score float64
		if json.Unmarshal(hit.ID, &id) != nil || json.Unmarshal(hit.Score, &score) != nil || !finite(score) {
			return false, false, "invalid_hit_id_or_score"
		}
		if id != truth[rank].ID || math.Abs(score-truth[rank].Score) > tolerance {
			truthOK = false
		}
		if withPayload {
			var payload returnedPayload
			pdec := json.NewDecoder(bytes.NewReader(hit.Payload))
			pdec.DisallowUnknownFields()
			if len(hit.Payload) == 0 || pdec.Decode(&payload) != nil || !returnedPayloadMatches(payload, id) {
				payloadOK = false
			}
		} else if len(hit.Payload) != 0 {
			payloadOK = false
		}
	}
	if !truthOK {
		return false, payloadOK, "candidate_id_or_score_mismatch"
	}
	if !payloadOK {
		return true, false, "payload_contract_mismatch"
	}
	return true, true, ""
}

func returnedPayloadMatches(got returnedPayload, id int64) bool {
	if got.ABIS == nil || got.Attributes == nil {
		return false
	}
	want := expectedPayloadForID(id)
	a, attrs := got.ABIS, got.Attributes
	return a.Active != nil && *a.Active == want.ABIS.Active &&
		a.BiometricRecordID != nil && *a.BiometricRecordID == want.ABIS.BiometricRecordID &&
		a.CollectionID != nil && *a.CollectionID == want.ABIS.CollectionID &&
		a.ModelVersion != nil && *a.ModelVersion == want.ABIS.ModelVersion &&
		a.NormalizationVersion != nil && *a.NormalizationVersion == want.ABIS.NormalizationVersion &&
		a.Operation != nil && *a.Operation == want.ABIS.Operation &&
		a.SubjectID != nil && *a.SubjectID == want.ABIS.SubjectID &&
		attrs.Position != nil && *attrs.Position == want.Attributes.Position &&
		attrs.Status != nil && *attrs.Status == want.Attributes.Status
}

func finishSample(row sample, dispatched, barrier time.Time) sample {
	finished := time.Now()
	row.LatencyMS = finished.Sub(dispatched).Seconds() * 1000
	row.CompletedS = finished.Sub(barrier).Seconds()
	return row
}

func countRow(doc *report, row sample, warmup bool) {
	if row.HTTPResponse {
		if warmup {
			doc.WarmupHTTPResponses++
		} else {
			doc.HTTPResponses++
		}
		doc.HTTPStatusCounts[strconv.Itoa(row.Status)]++
		if row.Protocol != "" {
			doc.ProtocolCounts[row.Protocol]++
		}
		if row.Status != http.StatusOK {
			if warmup {
				doc.WarmupHTTPErrorRequests++
			} else {
				doc.HTTPErrorRequests++
			}
		}
		if row.Status == http.StatusTooManyRequests {
			if warmup {
				doc.WarmupHTTP429Count++
			} else {
				doc.HTTP429Count++
			}
		}
	}
	if row.Protocol != "" && row.Protocol != "HTTP/1.1" {
		doc.ProtocolErrors++
	}
	if row.Failure == "timeout" {
		doc.TransportTimeouts++
	}
	if row.Failure == "transport_error" {
		doc.TransportFailures++
	}
	if strings.HasPrefix(row.Failure, "candidate_") || strings.Contains(row.Failure, "payload") || strings.Contains(row.Failure, "result_") || strings.Contains(row.Failure, "hit_") || strings.Contains(row.Failure, "invalid_response") {
		doc.CorrectnessFailed++
	}
	if row.Failure != "" {
		doc.FailureCounts[row.Failure]++
	}
	if warmup {
		doc.WarmupExactTruthMatches += row.TruthMatches
		doc.WarmupPayloadMatches += row.PayloadHits
		return
	}
	doc.DispatchedRequests++
	doc.DispatchedQueries += row.Queries
	doc.ExactQueryTruthMatches += row.TruthMatches
	doc.PayloadContractMatches += row.PayloadHits
	doc.SuccessfulQueries += row.ValidQueries
	if row.Success {
		doc.SuccessfulRequests++
	} else {
		doc.FailedRequests++
	}
}

func appendFailure(doc *report, row sample) {
	if len(doc.Failures) >= failureDetailLimit {
		doc.FailureDetailsOmitted++
		return
	}
	doc.Failures = append(doc.Failures, failureDetail{RequestIndex: row.RequestIndex, HTTPStatus: row.Status, Failure: row.Failure, QueryStart: row.QueryStart})
}

func finishReport(doc *report, _ time.Time, cfg config) {
	doc.FinishedUTC = time.Now().UTC().Format(time.RFC3339Nano)
	doc.SuccessfulHTTPRPS = 0
	doc.QueryQPS = 0
	if doc.ActualElapsedS > 0 {
		doc.SuccessfulHTTPRPS = float64(doc.SuccessfulRequests) / doc.ActualElapsedS
		doc.QueryQPS = float64(doc.SuccessfulRequests*cfg.batchSize) / doc.ActualElapsedS
	}
	doc.FailedQueries = doc.DispatchedQueries - doc.SuccessfulQueries
	doc.Passed = doc.Status == "COMPLETED" && doc.FailedRequests == 0 &&
		doc.SuccessfulRequests == doc.DispatchedRequests &&
		doc.SuccessfulQueries == doc.DispatchedQueries &&
		doc.ExactQueryTruthMatches == doc.DispatchedQueries &&
		doc.WarmupFailedRequests == 0 && doc.WarmupSuccesses == doc.WarmupConfigured &&
		doc.WarmupSuccessfulQueries == doc.WarmupQueries &&
		doc.WarmupExactTruthMatches == doc.WarmupQueries
	if exe, err := os.Executable(); err == nil {
		if raw, err := os.ReadFile(filepath.Clean(exe)); err == nil {
			h := sha256.Sum256(raw)
			doc.ExecutableSHA256 = hex.EncodeToString(h[:])
		} else {
			doc.ExecutableSHA256Error = err.Error()
		}
	} else {
		doc.ExecutableSHA256Error = err.Error()
	}
	doc.ThroughputBasis = "closed-loop successful HTTP responses / monotonic time from measurement barrier through final body validation; actual_elapsed_s includes drain; query_qps = successful requests * batch size / actual_elapsed_s"
}

func summarizeLatencies(values []float64) latencyStats {
	if len(values) == 0 {
		return latencyStats{Count: 0}
	}
	sorted := append([]float64(nil), values...)
	sort.Float64s(sorted)
	mean := 0.0
	for _, v := range sorted {
		mean += v
	}
	mean /= float64(len(sorted))
	return latencyStats{Count: len(sorted), P50MS: percentile(sorted, .50), P95MS: percentile(sorted, .95), P99MS: percentile(sorted, .99), MeanMS: &mean, MaxMS: &sorted[len(sorted)-1]}
}

func percentile(values []float64, p float64) *float64 {
	if len(values) == 0 {
		return nil
	}
	idx := int(math.Ceil(p*float64(len(values)))) - 1
	if idx < 0 {
		idx = 0
	}
	if idx >= len(values) {
		idx = len(values) - 1
	}
	v := values[idx]
	return &v
}

func writeReport(path string, doc report) error {
	b, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return writeOutput(path, append(b, '\n'))
}

func writeOutput(path string, data []byte) error {
	if path == "" {
		_, err := os.Stdout.Write(data)
		return err
	}
	return os.WriteFile(path, data, 0o600)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(2)
}
