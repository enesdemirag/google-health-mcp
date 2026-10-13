import asyncio


async def call(oauth, account, name, **arguments):
    response = await oauth.rpc(account["access_token"], "tools/call", {"name": name, "arguments": arguments})
    assert response.status_code == 200, response.text
    return response.json()["result"]


async def test_tool_catalog_has_english_schemas_and_read_only_annotations(oauth):
    account = await oauth.login()
    initialized = await oauth.rpc(
        account["access_token"],
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "contract-test", "version": "1"},
        },
    )
    assert initialized.status_code == 200
    response = await oauth.rpc(account["access_token"], "tools/list")
    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "get_connection_status",
        "list_health_metrics",
        "get_metric_history",
        "get_sleep_sessions",
        "get_workouts",
        "get_health_overview",
        "get_daily_health_context",
    }
    for tool in tools:
        assert tool["description"] and tool["outputSchema"]
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["destructiveHint"] is False
        assert "user_id" not in tool["inputSchema"]["properties"]
        assert "access_token" not in tool["inputSchema"]["properties"]


async def test_http_tools_isolate_concurrent_google_accounts_and_partial_consent(oauth):
    first, second = await oauth.login("a"), await oauth.login("b")
    results = await asyncio.gather(
        *[
            call(
                oauth,
                account,
                "get_metric_history",
                metric="steps",
                start_date="2026-10-12",
                end_date="2026-10-14",
                timezone="Europe/Istanbul",
            )
            for account in [first, second, first, second]
        ]
    )
    for result in results[::2]:
        data = result["structuredContent"]
        assert data["samples"] == [{"date": "2026-10-12", "value": 8120}]
        assert data["missing_dates"] == ["2026-10-13"]
        assert data["statistics"]["total"] == 8120
    for result in results[1::2]:
        assert result["structuredContent"]["status"] == "missing_permission"
        assert result["structuredContent"]["samples"] == []
    health_requests = [request for request in oauth.calls if "health.googleapis.com" in str(request.url)]
    assert all(request.headers["Authorization"] == "Bearer google-person-a" for request in health_requests)
    assert all(
        "google-person" not in str(result) and "private-refresh" not in str(result) for result in results
    )


async def test_connection_overview_and_optional_session_permissions(oauth):
    account = await oauth.login()
    status = (await call(oauth, account, "get_connection_status"))["structuredContent"]
    assert status["status"] == "connected" and status["health_account_linked"] is True
    catalog = (await call(oauth, account, "list_health_metrics"))["structuredContent"]
    assert len(catalog["metrics"]) == 17
    sleep = (
        await call(oauth, account, "get_sleep_sessions", start_date="2026-10-12", end_date="2026-10-14")
    )["structuredContent"]
    assert sleep["status"] == "missing_permission"
    workouts = (await call(oauth, account, "get_workouts", start_date="2026-10-12", end_date="2026-10-14"))[
        "structuredContent"
    ]
    assert workouts["status"] == "no_data"
    overview = (
        await call(
            oauth,
            account,
            "get_health_overview",
            start_date="2026-10-12",
            end_date="2026-10-14",
            metrics=["steps", "hrv"],
        )
    )["structuredContent"]
    assert [item["status"] for item in overview["metrics"]] == ["available", "missing_permission"]


async def test_two_authorized_users_receive_only_their_own_records(oauth):
    first, second = await oauth.login("a"), await oauth.login("c")
    results = await asyncio.gather(
        *[
            call(
                oauth,
                account,
                "get_metric_history",
                metric="steps",
                start_date="2026-10-12",
                end_date="2026-10-14",
            )
            for account in [first, second, first, second]
        ]
    )
    assert [result["structuredContent"]["samples"][0]["value"] for result in results] == [8120, 99, 8120, 99]
    headers = {
        request.headers["Authorization"]
        for request in oauth.calls
        if "health.googleapis.com" in str(request.url)
    }
    assert headers == {"Bearer google-person-a", "Bearer google-person-c"}


async def test_zero_health_consent_is_distinct_from_empty_health_records(oauth):
    account = await oauth.login("none")
    response = (await call(oauth, account, "get_connection_status"))["structuredContent"]
    assert response["status"] == "missing_permission"
    assert response["health_account_linked"] is None
    assert not any("health.googleapis.com" in str(request.url) for request in oauth.calls)


async def test_invalid_queries_do_not_reach_google(oauth):
    account = await oauth.login()
    before = sum("health.googleapis.com" in str(request.url) for request in oauth.calls)
    for arguments in [
        {"metric": "../../identity", "start_date": "2026-10-12", "end_date": "2026-10-14"},
        {"metric": "steps", "start_date": "2026-10-12", "end_date": "2026-10-12"},
        {"metric": "steps", "start_date": "2026-01-01", "end_date": "2026-10-14"},
        {"metric": "steps", "start_date": "2026-10-12", "end_date": "2026-10-14", "timezone": "invalid/zone"},
        {"metric": "steps", "start_date": "2026-10-12", "end_date": "2026-10-14", "user_id": "another-user"},
    ]:
        result = await call(oauth, account, "get_metric_history", **arguments)
        assert result.get("isError") is True
    assert sum("health.googleapis.com" in str(request.url) for request in oauth.calls) == before


async def test_http_origin_guard_blocks_untrusted_origin(oauth):
    account = await oauth.login()
    response = await oauth.client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {account['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Origin": "https://attacker.example",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 403
