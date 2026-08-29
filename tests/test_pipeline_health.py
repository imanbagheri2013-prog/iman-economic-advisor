from iea.health import overall_status

def test_pipeline_health_status():
results = [
{
"provider": "fred",
"series_id": "TEST_FRED",
"record_count": 1,
"missing_count": 0,
"status": "HEALTHY",
},
{
"provider": "bls",
"series_id": "TEST_BLS",
"record_count": 1,
"missing_count": 0,
"status": "HEALTHY",
},
]

```
status = overall_status(results)

assert status == "HEALTHY"
```

def test_pipeline_health_warning():
results = [
{
"provider": "fred",
"series_id": "TEST_FRED",
"record_count": 1,
"missing_count": 0,
"status": "HEALTHY",
},
{
"provider": "bls",
"series_id": "TEST_BLS",
"record_count": 1,
"missing_count": 1,
"status": "WARNING",
},
]

```
status = overall_status(results)

assert status == "WARNING"
```

def test_pipeline_health_critical():
results = [
{
"provider": "fred",
"series_id": "TEST_FRED",
"record_count": 0,
"missing_count": 0,
"status": "CRITICAL",
}
]

```
status = overall_status(results)

assert status == "CRITICAL"
```
