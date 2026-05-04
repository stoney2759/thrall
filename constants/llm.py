MAX_RETRIES = 3
RETRY_BASE_SECONDS = 5  # doubles each attempt: 5, 10, 20
RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})
