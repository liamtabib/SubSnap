# SubSnap Test Suite

This directory contains the complete test suite for SubSnap Reddit Email Digest.

## Test Files

### Core Integration Tests
- **`test_web_search.py`** - Web search integration and scoring system tests
- **`test_full_integration.py`** - End-to-end integration tests
- **`test_edge_cases.py`** - Edge case and error handling tests

### Feature-Specific Tests
- **`test_image_detection.py`** - Image analysis and detection tests
- **`test_multimodal.py`** - Multimodal AI summarization tests
- **`validate_scoring.py`** - Web search scoring validation with real examples

### Test Utilities
- **`run_tests.py`** - Test runner script for the entire suite

## Running Tests

### Run All Tests
```bash
cd tests
python run_tests.py
```

### Run Specific Test
```bash
cd tests
python run_tests.py --test web_search
```

### Run Individual Test Files
```bash
cd tests
python test_web_search.py
python test_full_integration.py
```

### Output Formats

#### Console Output (Default)
```bash
python test_web_search.py
# or
python run_tests.py --format=console
```

#### JSON Output
```bash
python test_web_search.py --format=json
# or
python run_tests.py --format=json --output=results.json
```

#### Quiet Output
```bash
python test_web_search.py --format=quiet
# or
python run_tests.py --format=quiet
```

## Test Output Files

Generated test output files are stored in the `../output/` directory:
- `test_email_output.html` - Sample HTML email output
- `test_email_output.txt` - Sample plain text email output

## Test Environment

Tests use the same configuration as the main application but with test-specific overrides:
- Web search is enabled in test mode for detailed logging
- Image analysis uses test mode settings
- API calls are mocked where appropriate to avoid costs

## Configuration

Most tests will work with minimal configuration, but for full functionality set:
```bash
export REDDIT_CLIENT_ID=your_client_id
export REDDIT_CLIENT_SECRET=your_client_secret
export OPENAI_API_KEY=your_openai_key
export EMAIL_PASSWORD=your_email_password
```

## Continuous Integration

For CI/CD pipelines, use quiet mode:
```bash
python run_tests.py --format=quiet
```

This will exit with code 0 on success, 1 on failure.