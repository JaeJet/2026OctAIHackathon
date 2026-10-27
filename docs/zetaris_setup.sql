-- Zetaris setup for the Minecraft crash investigator.
-- Run once in the Zetaris SQL Editor (http://localhost:3000), one statement at a time.
-- Source data: data/known_issues.json in this repo (built from the Data lead's sheet
-- by tools/csv_to_json.py). Descriptions may only use letters, numbers, spaces and _ . - ,

-- 1. A Lightning database that reads from a REST endpoint
CREATE LIGHTNING DATABASE MCCRASH_REST DESCRIBE BY "Minecraft crash known issues from the Data lead sheet";

-- 2. The known issues table, fetched from the JSON file on GitHub
CREATE LIGHTNING REST TABLE known_issues FROM MCCRASH_REST REQUEST(
    endpoint "https://raw.githubusercontent.com/JaeJet/2026OctAIHackathon/main/data/known_issues.json",
    method "get", response_type "json", http_encoding "URLENCODED"
) HEADER ( ) BODY ();

-- 3. A schema store container and the view the agent queries
CREATE SCHEMASTORE CONTAINER mccrash;
CREATE SCHEMASTORE VIEW known_issues_table WITH CONTAINER mccrash AS
SELECT id, name, aliases, signature, cause, fix, source_url, loader, mc_version, mod
FROM mccrash_rest.known_issues;

-- 4. Check: should return 25 rows (KI001 to KI025)
SELECT * FROM mccrash.known_issues_table;

-- The agent runs this query at the start of every investigation (agent/knowledge.py):
-- SELECT id, name, signature, cause, fix, source_url FROM mccrash.known_issues_table