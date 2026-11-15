# newehancement.md acceptance test guide

Maps §15 (job search) and §26 (competitive analysis) to automated tests and to manual steps.

- **Auto** = a test in `testing/` or `tests/`. Run `./testing/run_all_tests.sh`.
- **Demo** = manual step in Demo Mode. Fixture data, no network, banner says illustrative.
- **Live** = manual step that needs `SERPAPI_API_KEY` (and an LLM key). Not covered by a real call in CI.

Start the app first: `source .venv/bin/activate && streamlit run app.py`, open **Workforce Studio**.

Sample labels used below:
- JOBS = "Find product manager jobs in Hyderabad (5–10 years, last 7 days)"
- RICH = "Compare product manager and product marketer (example company context)"
- THIN = "Compare product manager and product marketer (needs context)"

---

## Part 1 — §15 Job search

| # | Criterion | Auto | Manual |
| --- | --- | --- | --- |
| 1 | Spec shows family `product_management`, Hyderabad/IN, 5–10 overlap, `posted_after` = retrieval − 7 days | `test_parse_intent_target_sentence`, `test_parse_experience_range`, `test_parse_posted_within_days`, `test_demo_graph_job_search_end_to_end` | **Demo:** select JOBS. Panel reads "Interpreted as: job search" with Min years 5, Max years 10, City Hyderabad, "Posted within (days, 0 = off)" 7. Run. In **Research** tab open the query echo: city, experience, `posted_after` shown. |
| 2 | Jobs request uses intent fields, not the raw sentence | `test_serpapi_params_come_from_intent` (checks `q`, `location`, `chips=date_posted:week`, `engine=google_jobs`, key) | **Live:** run JOBS. Run Log shows the SerpAPI query echo built from the fields. |
| 3 | Every row has `job_id`, company, description from the payload | `test_serpapi_maps_results_to_job_records`, `test_review_identity_and_grounding_and_role_and_place`, `test_live_research_builds_envelope_in_code_from_tool_payload` | **Live:** open Deliverable → every included row has company and a description. Rows lacking a source id never appear. |
| 4 | No project manager / product marketing manager etc. included | `test_pm_family_included`, `test_pm_family_excluded`, `test_apply_job_filters_split_and_counts` | **Demo:** Deliverable → Excluded groups lists "out of family" with titles such as Project Manager and Product Marketing Manager. None in the main table. |
| 5 | Only Hyderabad (or alias) in included | `test_location_uses_job_fields_not_employer_text`, `test_location_locality_alias_and_city`, `test_hyderabad_sindh_is_not_hyderabad_telangana` | **Demo:** excluded group "wrong city" shows the non-Hyderabad fixture. Change the city to Bengaluru in the panel and re-run to see the table change. |
| 6 | No row older than 7 days or with no date | `test_relative_posted_labels_use_retrieval_time`, `test_recency_boundary_and_stale`, `test_apply_job_filters_split_and_counts` | **Demo:** excluded group "stale" is listed. Set "Posted within (days, 0 = off)" to 3 and re-run; the count of included rows drops. |
| 7 | Experience must overlap 5–10; unknown goes to `needs_review` | `test_experience_overlap_table`, `test_unknown_experience_never_in_main_table`, `test_experience_parsed_from_description_when_not_structured`, `test_source_experience_conflict_keeps_nearest_to_experience_no_average` | **Demo:** "Needs review" table holds the row with no years stated. Excluded group "no experience overlap" is listed. Included rows all show an experience that overlaps 5–10. |
| 8 | Apply URLs not in the payload are absent | `test_ground_envelope_drops_invented_ids_and_urls`, `test_scrub_ungrounded_refs`, `test_execution_drops_invented_refs_and_renders_markdown_from_envelope` | **Demo:** Deliverable apply links are `example.invalid` only. Use **Request Revision** with the note "add a link to the Acme careers page"; the new draft must not contain it. |
| 9 | Truncated descriptions labelled, not completed | `test_truncated_description_is_labelled_not_completed` | **Live:** a row whose snippet ends with "…" shows the truncated caption; text is not extended. |
| 10 | Zero survivors → exclusion counts, no invented listing | `test_duplicate_ids_collapsed_and_empty_set_explained`, `test_review_empty_set_with_explanations_passes_but_dropped_rows_fail`, `test_live_source_failure_is_empty_contribution_not_fabrication` | **Demo:** set Min years 40 and Max years 45, then Run. Included table is empty (one "needs review" row with no stated years may remain); the summary line and excluded groups explain why. |
| 11 | Demo runs same screens, fixture ids, banner, no network | `test_demo_envelope_shows_the_filters_without_network`, `test_demo_research_never_touches_jobs_provider_or_llm`, `test_demo_graph_job_search_end_to_end` | **Demo:** Deliverable begins with the illustrative banner; ids are `demo-hyd-pm-*`. Disconnect Wi-Fi and run again; it still completes. |
| 12 | Stops at human approval; nothing applies to a job | `test_demo_graph_job_search_end_to_end` (status `AWAITING_HUMAN_APPROVAL`, `approval_status` unset), `test_review_flags_safety_claims_and_invented_text` | Run ends with the Approve / Request Revision / Reject panel visible. The status shows awaiting approval. No button anywhere applies to a job. |

### Related checks (beyond §15)

| Behaviour | Auto | Manual |
| --- | --- | --- |
| Live without `SERPAPI_API_KEY` fails clearly, never falls back to demo | `test_live_job_search_without_key_fails_clearly`, `test_live_graph_job_search_fails_clearly_without_key`, `test_run_service_blocks_live_job_search_without_serpapi_key`, `test_serpapi_not_configured_raises_clearly` | Unset the key, switch to Live, select JOBS. The panel shows an error naming `SERPAPI_API_KEY`; Run is blocked. |
| Key never leaks in errors | `test_serpapi_http_error_does_not_leak_key` | Use an invalid key in `.env`; the error text does not contain it. |
| CSV of included jobs | `test_csv_export_of_included_jobs_and_bundle` | After a JOBS run click **Download CSV (included jobs)**. Columns: `job_id,title,company,city,date_posted,experience,apply_url`. |
| Briefing path unchanged | `test_briefing_path_unchanged`, `test_briefing_runs_keep_default_task_class` | Select any non-job sample; no "Interpreted as" panel; output has the usual tabs. |
| User corrections override parsing | `test_user_confirmed_intent_is_used` | Change Max years to 8 in the panel; the run's query echo shows 8. |

---

## Part 2 — §26 Competitive analysis

| # | Criterion | Auto | Manual |
| --- | --- | --- | --- |
| 1 | Spec: kind `role`, subjects PM and PMM, hiring decision, company/market/team/ownership lines | `test_rich_context_intent_matches_section_19`, `test_canonical_subjects_map_synonyms_and_flag_lookalikes`, `test_context_echo_lines`, `test_user_confirmed_comparison_intent_is_used` | **Demo:** select RICH. Panel reads "Interpreted as: competitive analysis" with both subjects, the decision, and the echoed context lines. |
| 2 | One cell per criterion per subject | `test_demo_matrix_has_one_cell_per_criterion_per_subject`, `test_every_non_empty_cell_has_a_basis_and_no_numeric_scores` | Run RICH. Deliverable matrix has six criteria rows (launch, positioning, enablement, roadmap, metrics, pricing) and two subject columns. |
| 3 | "Release notes" / "first sales call" are `user_supplied` on PM, quoting the user | `test_user_context_outranks_domain_default`, `test_demo_matrix_has_one_cell_per_criterion_per_subject` | In the matrix, PM launch/enablement cells carry basis `user_supplied` and quote your wording. |
| 4 | "No product marketer today" is `user_supplied` on PMM | `test_rich_context_intent_matches_section_19`, `test_user_context_outranks_domain_default` | PMM current-state cells show `user_supplied` with the "no product marketer" statement. |
| 5 | Usual ownership only as `domain_default`, label visible | `test_every_non_empty_cell_has_a_basis_and_no_numeric_scores`, `test_review_basis_blanks_and_precedence` | Positioning cells carry a visible "usual practice (domain default)" label. Never presented as company fact. |
| 6 | Topic not mentioned (pricing owner) is `unknown`/absent for company cells | `test_unknown_cells_stay_empty_and_are_listed` | Pricing row company cells are blank. "Unknowns" lists pricing owner. |
| 7 | Public URLs only from the search tool; Demo has none | `test_demo_research_makes_no_search_calls`, `test_live_research_attaches_only_tool_urls_per_criterion` | **Demo:** no URLs in evidence. **Live:** every evidence URL appears in the Run Log search results. |
| 8 | Options address one headcount; no candidate or job ad | `test_options_address_the_decision_without_naming_candidates_or_ads`, `test_review_safety_job_ad_and_opened_role` | Options are "Hire a product marketer / Hire a product manager / Defer". None names a person or drafts an ad. |
| 9 | Blank context → `needs_context`, empty matrix, generic frame | `test_thin_context_needs_context_with_unblock_questions`, `test_thin_context_returns_labelled_domain_frame_and_empty_matrix`, `test_needs_context_markdown_labels_frame_as_generic`, `test_demo_graph_thin_comparison_waits_for_context_and_passes_review` | **Demo:** select THIN. Panel shows a warning "Context is thin…" and the questions. Run. Deliverable shows a domain frame banner marked generic and no contextual matrix. |
| 10 | Stops at human approval | `test_demo_graph_rich_comparison_end_to_end`, `test_competitive_analysis_demo_branches_and_thin_context_waits` | Both RICH and THIN end at Approve / Request Revision / Reject. |

### Related checks (beyond §26)

| Behaviour | Auto | Manual |
| --- | --- | --- |
| Project manager is not silently treated as product manager | `test_project_manager_is_not_silently_accepted_as_pm` | Task "Compare project manager and product marketer": the Subjects field shows "Project Manager" (not "Product Manager"), so you can see and correct it. It is never silently remapped. |
| Adding context unblocks the run | `test_rebuild_after_user_corrections_clears_needs_context` | From THIN, fill Background and Constraints with the RICH text; warning disappears; status becomes ready after run. |
| Compare vs job-search routing | `test_classification_comparison_vs_job_search`, `test_samples_classify_as_designed` | "Compare PM jobs in Hyderabad" must not be classed as comparison unless ≥2 subjects are parsed. |
| Product comparison needs user criteria | `test_product_comparison_uses_user_listed_criteria_with_unknown_cells` | Task "Compare RazorpayX and Cashfree for our payouts page." with Background "We sell to the same mid-market finance buyer. The decision is what to say on our pricing page this quarter. Here are the three criteria I care about: settlement time, who the buyer is, and what they charge for vendor payouts." The matrix has those three rows and every cell is blank/unknown. |
| Matrix CSV | `test_comparison_csv_and_bundle_export` | **Download CSV (matrix cells)** → columns `criterion,subject,finding,basis,confidence`. |
