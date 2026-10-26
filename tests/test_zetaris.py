from agent.zetaris import rows


def test_rows_pairs_headers_with_values():
    reply = {"headers": ["id", "signature"],
             "data": [["KI001", "for invalid dist DEDICATED_SERVER"],
                      ["KI002", "Missing or unsupported mandatory dependencies:"]],
             "total": 2, "timeUsed": 5085}
    assert rows(reply) == [
        {"id": "KI001", "signature": "for invalid dist DEDICATED_SERVER"},
        {"id": "KI002", "signature": "Missing or unsupported mandatory dependencies:"},
    ]


def test_rows_empty_reply():
    assert rows({"headers": ["id"], "data": [], "total": 0}) == []