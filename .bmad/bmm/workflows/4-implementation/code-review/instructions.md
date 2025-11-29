# Senior Developer Review - Workflow Instructions

````xml
<critical>The workflow execution engine is governed by: {project-root}/.bmad/core/tasks/workflow.xml</critical>
<critical>You MUST have already loaded and processed: {installed_path}/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language} and language MUST be tailored to {user_skill_level}</critical>
<critical>Generate all documents in {document_output_language}</critical>
<critical>This workflow performs a SYSTEMATIC Senior Developer Review on a story with status "review", validates EVERY acceptance criterion and EVERY completed task, appends structured review notes with evidence, and updates the story status based on outcome.</critical>
<critical>If story_path is provided, use it. Otherwise, find the first story in sprint-status.yaml with status "review". If none found, offer ad-hoc review option.</critical>
<critical>Ad-hoc review mode: User can specify any files to review and what to review for (quality, security, requirements, etc.). Creates standalone review report.</critical>
<critical>SYSTEMATIC VALIDATION REQUIREMENT: For EVERY acceptance criterion, verify implementation with evidence (file:line). For EVERY task marked complete, verify it was actually done. Tasks marked complete but not done = HIGH SEVERITY finding.</critical>
<critical>⚠️ ZERO TOLERANCE FOR LAZY VALIDATION ⚠️</critical>
<critical>If you FAIL to catch even ONE task marked complete that was NOT actually implemented, or ONE acceptance criterion marked done that is NOT in the code with evidence, you have FAILED YOUR ONLY PURPOSE. This is an IMMEDIATE DISQUALIFICATION. No shortcuts. No assumptions. No "looks good enough." You WILL read every file. You WILL verify every claim. You WILL provide evidence (file:line) for EVERY validation. Failure to catch false completions = you failed humanity and the project. Your job is to be the uncompromising gatekeeper. DO YOUR JOB COMPLETELY OR YOU WILL BE REPLACED.</critical>
<critical>Only modify the story file in these areas: Status, Dev Agent Record (Completion Notes), File List (if corrections needed), Change Log, and the appended "Senior Developer Review (AI)" section.</critical>
<critical>Execute ALL steps in exact order; do NOT skip steps</critical>

<critical>DOCUMENT OUTPUT: Technical review reports. Structured findings with severity levels and action items. User skill level ({user_skill_level}) affects conversation style ONLY, not review content.</critical>

<workflow>

  <step n="1" goal="Find story ready for review" tag="sprint-status">
    <check if="{{story_path}} is provided">
      <action>Use {{story_path}} directly</action>
      <action>Read COMPLETE story file and parse sections</action>
      <action>Extract story_key from filename or story metadata</action>
      <action>Verify Status is "review" or "ready-for-review" - if not, HALT with message: "Story status must be 'review' or 'ready-for-review' to proceed"</action>
    </check>

    <check if="{{story_path}} is NOT provided">
      <critical>MUST read COMPLETE sprint-status.yaml file from start to end to preserve order</critical>
      <action>Load the FULL file: {{output_folder}}/sprint-status.yaml</action>
      <action>Read ALL lines from beginning to end - do not skip any content</action>
      <action>Parse the development_status section completely</action>

      <action>Find FIRST story (reading in order from top to bottom) where:
        - Key matches pattern: number-number-name (e.g., "1-2-user-auth")
        - NOT an epic key (epic-X) or retrospective (epic-X-retrospective)
        - Status value equals "review" OR "ready-for-review"
      </action>

      <check if="no story with status 'review' or 'ready-for-review' found">
        <output>📋 No stories with status "review" or "ready-for-review" found

**What would you like to do?**
1. Run `dev-story` to implement and mark a story ready for review
2. Check sprint-status.yaml for current story states
3. Tell me what code to review and what to review it for
        </output>
        <ask>Select an option (1/2/3):</ask>

        <check if="option 3 selected">
          <ask>What code would you like me to review?

          Provide:
          - File path(s) or directory to review
          - What to review for:
            • General quality and standards
            • Requirements compliance
            • Security concerns
            • Performance issues
            • Architecture alignment
            • Something else (specify)

            Your input:?
          </ask>

          <action>Parse user input to extract:
            - {{review_files}}: file paths or directories to review
            - {{review_focus}}: what aspects to focus on
            - {{review_context}}: any additional context provided
          </action>

          <action>Set ad_hoc_review_mode = true</action>
          <action>Skip to step 4 with custom scope</action>
        </check>

        <check if="option 1 or 2 or no option 3">
          <action>HALT</action>
        </check>
      </check>

      <action>Use the first story found with status "review"</action>
      <action>Resolve story file path in {{story_dir}}</action>
      <action>Read the COMPLETE story file</action>
    </check>

    <action>Extract {{epic_num}} and {{story_num}} from filename (e.g., story-2.3.*.md) and story metadata</action>
    <action>Parse sections: Status, Story, Acceptance Criteria, Tasks/Subtasks (and completion states), Dev Notes, Dev Agent Record (Context Reference, Completion Notes, File List), Change Log</action>
    <action if="story cannot be read">HALT with message: "Unable to read story file"</action>
  </step>

  <step n="1.5" goal="Discover and load project documents">
    <invoke-protocol name="discover_inputs" />
    <note>After discovery, these content variables are available: {architecture_content}, {ux_design_content}, {epics_content} (loads only epic for this story if sharded), {document_project_content}</note>
  </step>

  <step n="2" goal="Resolve story context file and specification inputs">
    <action>Locate story context file: Under Dev Agent Record → Context Reference, read referenced path(s). If missing, search {{output_folder}} for files matching pattern "story-{{epic_num}}.{{story_num}}*.context.xml" and use the most recent.</action>
    <action if="no story context file found">Continue but record a WARNING in review notes: "No story context file found"</action>

    <action>Locate Epic Tech Spec: Search {{tech_spec_search_dir}} with glob {{tech_spec_glob_template}} (resolve {{epic_num}})</action>
    <action if="no tech spec found">Continue but record a WARNING in review notes: "No Tech Spec found for epic {{epic_num}}"</action>

    <action>Load architecture/standards docs: For each file name in {{arch_docs_file_names}} within {{arch_docs_search_dirs}}, read if exists. Collect testing, coding standards, security, and architectural patterns.</action>
    <note>Architecture and brownfield docs were pre-loaded in Step 1.5 as {architecture_content} and {document_project_content}</note>
  </step>

  <step n="3" goal="Detect tech stack and establish best-practice reference set">
    <action>Detect primary ecosystem(s) by scanning for manifests (e.g., package.json, pyproject.toml, go.mod, Dockerfile). Record key frameworks (e.g., Node/Express, React/Vue, Python/FastAPI, etc.).</action>
    <action>Synthesize a concise "Best-Practices and References" note capturing any updates or considerations that should influence the review (cite links and versions if available).</action>
  </step>

  <step n="4" goal="Systematic validation of implementation against acceptance criteria and tasks">
    <check if="ad_hoc_review_mode == true">
      <action>Use {{review_files}} as the file list to review</action>
      <action>Focus review on {{review_focus}} aspects specified by user</action>
      <action>Use {{review_context}} for additional guidance</action>
      <action>Skip acceptance criteria checking (no story context)</action>
      <action>If architecture docs exist, verify alignment with architectural constraints</action>
    </check>

    <check if="ad_hoc_review_mode != true">
      <critical>SYSTEMATIC VALIDATION - Check EVERY AC and EVERY task marked complete</critical>

      <action>From the story, read Acceptance Criteria section completely - parse into numbered list</action>
      <action>From the story, read Tasks/Subtasks section completely - parse ALL tasks and subtasks with their completion state ([x] = completed, [ ] = incomplete)</action>
      <action>From Dev Agent Record → File List, compile list of changed/added files. If File List is missing or clearly incomplete, search repo for recent changes relevant to the story scope (heuristics: filenames matching components/services/routes/tests inferred from ACs/tasks).</action>

      <critical>Step 4A: SYSTEMATIC ACCEPTANCE CRITERIA VALIDATION</critical>
      <action>Create AC validation checklist with one entry per AC</action>
      <action>For EACH acceptance criterion (AC1, AC2, AC3, etc.):
        1. Read the AC requirement completely
        2. Search changed files for evidence of implementation
        3. Determine: IMPLEMENTED, PARTIAL, or MISSING
        4. Record specific evidence (file:line references where AC is satisfied)
        5. Check for corresponding tests (unit/integration/E2E as applicable)
        6. If PARTIAL or MISSING: Flag as finding with severity based on AC criticality
        7. Document in AC validation checklist
      </action>
      <action>Generate AC Coverage Summary: "X of Y acceptance criteria fully implemented"</action>

      <critical>Step 4B: SYSTEMATIC TASK COMPLETION VALIDATION</critical>
      <action>Create task validation checklist with one entry per task/subtask</action>
      <action>For EACH task/subtask marked as COMPLETED ([x]):
        1. Read the task description completely
        2. Search changed files for evidence the task was actually done
        3. Determine: VERIFIED COMPLETE, QUESTIONABLE, or NOT DONE
        4. Record specific evidence (file:line references proving task completion)
        5. **CRITICAL**: If marked complete but NOT DONE → Flag as HIGH SEVERITY finding with message: "Task marked complete but implementation not found: [task description]"
        6. If QUESTIONABLE → Flag as MEDIUM SEVERITY finding: "Task completion unclear: [task description]"
        7. Document in task validation checklist
      </action>
      <action>For EACH task/subtask marked as INCOMPLETE ([ ]):
        1. Note it was not claimed to be complete
        2. Check if it was actually done anyway (sometimes devs forget to check boxes)
        3. If done but not marked: Note in review (helpful correction, not a finding)
      </action>
      <action>Generate Task Completion Summary: "X of Y completed tasks verified, Z questionable, W falsely marked complete"</action>

      <critical>Step 4C: CROSS-CHECK EPIC TECH-SPEC REQUIREMENTS</critical>
      <action>Cross-check epic tech-spec requirements and architecture constraints against the implementation intent in files.</action>
      <action if="critical architecture constraints are violated (e.g., layering, dependency rules)">flag as High Severity finding.</action>

      <critical>Step 4D: COMPILE VALIDATION FINDINGS</critical>
      <action>Compile all validation findings into structured list:
        - Missing AC implementations (severity based on AC importance)
        - Partial AC implementations (MEDIUM severity)
        - Tasks falsely marked complete (HIGH severity - this is critical)
        - Questionable task completions (MEDIUM severity)
        - Missing tests for ACs (severity based on AC criticality)
        - Architecture violations (HIGH severity)
      </action>
    </check>
  </step>

  <step n="4.5" goal="Zero-Mock Enforcement - detect placeholder and mock implementations">
    <critical>ZERO-MOCK ENFORCEMENT: Every mock is technical debt. Every stub is a lie to users. Every placeholder is a broken promise.</critical>
    <critical>The Five Absolutes - violations are HIGH severity and BLOCK approval:
      1. NEVER return hardcoded values in production code
      2. NEVER write validation that always succeeds
      3. NEVER simulate when you should calculate
      4. NEVER stub when you should implement
      5. NEVER claim completion for incomplete work
      6. NEVER simplify a test to avoid an error
    </critical>

    <action>Create zero-mock validation checklist for all changed/added files</action>

    <action>**4.5A - Hardcoded Return Values Detection:**
      Search all changed files for patterns indicating hardcoded returns:
      - `return 10`, `return 1.0`, `return 0`, `return True`, `return False` (without logic)
      - `return []`, `return {}`, `return None` (when real data expected)
      - Any return statement with inline comment like "# Will implement later", "# TODO", "# Mock"

      For EACH occurrence:
      1. Determine if it's a legitimate default/sentinel OR a placeholder
      2. If placeholder: Flag as HIGH SEVERITY with evidence (file:line)
      3. Record in zero-mock checklist: Pattern | File:Line | Status (VIOLATION/OK) | Justification
    </action>

    <action>**4.5B - Always-Succeeding Validation Detection:**
      Search for validation/check functions that always return True or never raise:
      - `def validate_*(...):\s*return True`
      - `def check_*(...):\s*return True`
      - `def is_valid*(...):\s*return True`
      - Validation functions with no conditional logic
      - Empty validation bodies or single `pass` statements

      For EACH occurrence:
      1. Verify the validation performs actual checks
      2. If always-succeeds: Flag as HIGH SEVERITY with evidence (file:line)
      3. Record in zero-mock checklist
    </action>

    <action>**4.5C - Mock/Stub/Fake Pattern Detection:**
      Search for mock indicators in variable names, function names, and comments:
      - Names containing: mock, fake, stub, dummy, placeholder, temp, hack
      - Comments containing: "# mock", "# fake", "# stub", "# TODO", "# FIXME", "# HACK"
      - TODO/FIXME/HACK comments WITHOUT associated issue tracking reference

      For EACH occurrence:
      1. Determine if it's test code (acceptable) or production code (violation)
      2. If production code mock: Flag as HIGH SEVERITY with evidence (file:line)
      3. If TODO/FIXME without issue reference: Flag as MEDIUM SEVERITY
      4. Record in zero-mock checklist
    </action>

    <action>**4.5D - Empty Error Handling Detection:**
      Search for error handling that silently swallows exceptions:
      - `except: pass`
      - `except Exception: pass`
      - `except *: ...` with empty or trivial body
      - `try: ... except: return None` (hiding errors)

      For EACH occurrence:
      1. Verify if exception handling is intentional and documented
      2. If silently swallowing: Flag as HIGH SEVERITY with evidence (file:line)
      3. Record in zero-mock checklist
    </action>

    <action>**4.5E - Simplified Implementation Detection:**
      Search for simplified implementations without proper warning blocks:
      - Functions that should compute but return constants
      - Algorithms that skip edge cases
      - Data processing that ignores validation

      Check for required warning format if simplified:
      ```
      # SIMPLIFIED IMPLEMENTATION - APPROVED BY: [Name] DATE: [Date] ISSUE: #XXX
      # REASON: [Specific reason]
      # WARNING: [Limitations]
      ```

      If simplified without proper warning block: Flag as HIGH SEVERITY
    </action>

    <action>**4.5F - Test Quality Verification:**
      For test files in changed files list, verify:
      - Tests exercise real functionality, not mocks of the code under test
      - Assertions compare against calculated expected values, not hardcoded magic numbers
      - Tests would fail if the implementation returned wrong values

      Patterns to flag:
      - `assert result == 10` without explanation of why 10 is expected
      - Extensive mocking of the system under test (mocking dependencies is OK)
      - Tests that cannot fail (no meaningful assertions)

      If mock-heavy tests found: Flag as MEDIUM SEVERITY
    </action>

    <action>Generate Zero-Mock Summary:
      - Total files scanned: X
      - Hardcoded returns found: X (list file:line)
      - Always-succeeding validations: X (list file:line)
      - Mock patterns in production: X (list file:line)
      - Empty error handlers: X (list file:line)
      - Simplified without warning: X (list file:line)
      - Mock-heavy tests: X (list file:line)
      - **ZERO-MOCK STATUS**: PASS (0 violations) | FAIL (X violations)
    </action>

    <check if="any HIGH severity zero-mock violations found">
      <action>Set review_blocked = true</action>
      <action>Add to Key Findings: "🚫 ZERO-MOCK VIOLATION: [count] placeholder/mock implementations detected. Review BLOCKED until resolved."</action>
    </check>
  </step>

  <step n="4.6" goal="Orphaned Files Enforcement - detect improperly placed files">
    <critical>ORPHANED FILES ENFORCEMENT: All files must be properly organized within the project structure. No files in root directory. No files in arbitrary locations.</critical>

    <action>Create orphaned files validation checklist for all new files created</action>

    <action>**4.6A - Root Directory File Detection:**
      Check if any NEW files were created directly in the project root directory:
      - Source files (.py, .js, .ts, .go, .rs, etc.) in root
      - Config files that should be in config/ or .config/
      - Data files that should be in data/ or assets/
      - Test files that should be in tests/

      Exceptions (OK in root):
      - Standard project files: README.md, LICENSE, .gitignore, pyproject.toml, package.json, Makefile, etc.
      - CI/CD configs: .github/, .gitlab-ci.yml, etc.

      For EACH new root file that's not a standard exception:
      1. Flag as HIGH SEVERITY with evidence (file path)
      2. Suggest proper location based on file type
      3. Record in orphaned files checklist
    </action>

    <action>**4.6B - Arbitrary Directory Placement Detection:**
      Check if any NEW files were placed in directories that don't match the project structure:
      - Source files outside src/ or designated source directories
      - Test files outside tests/ or designated test directories
      - Documentation outside docs/ when docs/ exists
      - Scripts outside scripts/ when scripts/ exists
      - Files in temp/, tmp/, scratch/, or similar non-production directories

      For EACH improperly placed file:
      1. Flag as MEDIUM SEVERITY with evidence (file path)
      2. Suggest proper location based on project conventions
      3. Record in orphaned files checklist
    </action>

    <action>**4.6C - Naming Convention Verification:**
      Check if new files follow project naming conventions:
      - Consistent case style (snake_case, kebab-case, camelCase) matching existing files
      - Descriptive names that indicate purpose
      - No generic names like: test.py, temp.js, foo.ts, bar.py, untitled.md
      - No numbered variants without context: file1.py, file2.py

      For EACH naming violation:
      1. Flag as LOW SEVERITY with evidence (file path)
      2. Suggest proper naming based on project conventions
      3. Record in orphaned files checklist
    </action>

    <action>**4.6D - Import/Reference Verification:**
      For each new file, verify it's properly integrated:
      - Is it imported/referenced by other files? (orphan detection)
      - Are there dangling references to files that don't exist?
      - Are there circular import issues introduced?

      For EACH orphaned file (created but never used):
      1. Determine if it's intentionally standalone (CLI, entry point) or forgotten
      2. If forgotten/unused: Flag as MEDIUM SEVERITY
      3. Record in orphaned files checklist
    </action>

    <action>Generate Orphaned Files Summary:
      - New files created: X
      - Files in root (violations): X (list paths)
      - Files in wrong directories: X (list paths)
      - Naming convention violations: X (list paths)
      - Orphaned/unused files: X (list paths)
      - **ORPHAN STATUS**: PASS (0 HIGH/MEDIUM violations) | FAIL (X violations)
    </action>

    <check if="any HIGH severity orphan violations found">
      <action>Set review_blocked = true</action>
      <action>Add to Key Findings: "🚫 ORPHANED FILES VIOLATION: [count] improperly placed files detected. Review BLOCKED until resolved."</action>
    </check>
  </step>

  <step n="5" goal="Perform code quality and risk review">
    <action>For each changed file, skim for common issues appropriate to the stack: error handling, input validation, logging, dependency injection, thread-safety/async correctness, resource cleanup, performance anti-patterns.</action>
    <action>Perform security review: injection risks, authZ/authN handling, secret management, unsafe defaults, un-validated redirects, CORS misconfigured, dependency vulnerabilities (based on manifests).</action>
    <action>Check tests quality: assertions are meaningful, edge cases covered, deterministic behavior, proper fixtures, no flakiness patterns.</action>
    <action>Capture concrete, actionable suggestions with severity (High/Med/Low) and rationale. When possible, suggest specific code-level changes (filenames + line ranges) without rewriting large sections.</action>
  </step>

  <step n="6" goal="Decide review outcome and prepare comprehensive notes">
    <action>Determine outcome based on validation results:
      - BLOCKED: Any HIGH severity finding (AC missing, task falsely marked complete, critical architecture violation, zero-mock violation, orphaned file in root)
      - CHANGES REQUESTED: Any MEDIUM severity findings or multiple LOW severity issues
      - APPROVE: All ACs implemented, all completed tasks verified, zero-mock PASS, orphan check PASS, no significant issues
    </action>

    <action>Prepare a structured review report with sections:
      1. **Summary**: Brief overview of review outcome and key concerns
      2. **Outcome**: Approve | Changes Requested | Blocked (with justification)
      3. **Key Findings** (by severity):
         - HIGH severity issues first (especially falsely marked complete tasks)
         - MEDIUM severity issues
         - LOW severity issues
      4. **Acceptance Criteria Coverage**:
         - Include complete AC validation checklist from Step 4A
         - Show: AC# | Description | Status (IMPLEMENTED/PARTIAL/MISSING) | Evidence (file:line)
         - Summary: "X of Y acceptance criteria fully implemented"
         - List any missing or partial ACs with severity
      5. **Task Completion Validation**:
         - Include complete task validation checklist from Step 4B
         - Show: Task | Marked As | Verified As | Evidence (file:line)
         - **CRITICAL**: Highlight any tasks marked complete but not done in RED/bold
         - Summary: "X of Y completed tasks verified, Z questionable, W falsely marked complete"
      6. **Zero-Mock Enforcement**:
         - Include complete zero-mock validation checklist from Step 4.5
         - Show: Check Type | File:Line | Status (VIOLATION/OK) | Details
         - Categories: Hardcoded returns, Always-succeeding validations, Mock patterns, Empty handlers, Simplified implementations, Test quality
         - Summary: "ZERO-MOCK STATUS: PASS/FAIL - X violations found"
         - **CRITICAL**: Any HIGH severity mock violation BLOCKS approval
      7. **Orphaned Files Enforcement**:
         - Include complete orphaned files checklist from Step 4.6
         - Show: File Path | Issue Type | Severity | Suggested Location
         - Categories: Root directory files, Wrong directory placement, Naming violations, Unused files
         - Summary: "ORPHAN STATUS: PASS/FAIL - X violations found"
         - **CRITICAL**: Any HIGH severity orphan violation BLOCKS approval
      8. **Test Coverage and Gaps**:
         - Which ACs have tests, which don't
         - Test quality issues found
      9. **Architectural Alignment**:
         - Tech-spec compliance
         - Architecture violations if any
      10. **Security Notes**: Security findings if any
      11. **Best-Practices and References**: With links
      12. **Action Items**:
          - CRITICAL: ALL action items requiring code changes MUST have checkboxes for tracking
          - Format for actionable items: `- [ ] [Severity] Description (AC #X) [file: path:line]`
          - Format for informational notes: `- Note: Description (no action required)`
          - Imperative phrasing for action items
          - Map to related ACs or files with specific line references
          - Include suggested owners if clear
          - Example format:
            ```
            ### Action Items

            **Code Changes Required:**
            - [ ] [High] Add input validation on login endpoint (AC #1) [file: src/routes/auth.js:23-45]
            - [ ] [Med] Add unit test for invalid email format [file: tests/unit/auth.test.js]

            **Advisory Notes:**
            - Note: Consider adding rate limiting for production deployment
            - Note: Document the JWT expiration policy in README
            ```
    </action>

    <critical>The AC validation checklist and task validation checklist MUST be included in the review - this is the evidence trail</critical>
  </step>

  <step n="7" goal="Append review to story and update metadata">
    <check if="ad_hoc_review_mode == true">
      <action>Generate review report as a standalone document</action>
      <action>Save to {{output_folder}}/code-review-{{date}}.md</action>
      <action>Include sections:
        - Review Type: Ad-Hoc Code Review
        - Reviewer: {{user_name}}
        - Date: {{date}}
        - Files Reviewed: {{review_files}}
        - Review Focus: {{review_focus}}
        - Outcome: (Approve | Changes Requested | Blocked)
        - Summary
        - Key Findings
        - Zero-Mock Enforcement (with checklist and summary)
        - Orphaned Files Enforcement (with checklist and summary)
        - Test Coverage and Gaps
        - Architectural Alignment
        - Security Notes
        - Best-Practices and References (with links)
        - Action Items
      </action>
      <output>Review saved to: {{output_folder}}/code-review-{{date}}.md</output>
    </check>

    <check if="ad_hoc_review_mode != true">
      <action>Open {{story_path}} and append a new section at the end titled exactly: "Senior Developer Review (AI)".</action>
      <action>Insert subsections:
        - Reviewer: {{user_name}}
        - Date: {{date}}
        - Outcome: (Approve | Changes Requested | Blocked) with justification
        - Summary
        - Key Findings (by severity - HIGH/MEDIUM/LOW)
        - **Acceptance Criteria Coverage**:
          * Include complete AC validation checklist with table format
          * AC# | Description | Status | Evidence
          * Summary: X of Y ACs implemented
        - **Task Completion Validation**:
          * Include complete task validation checklist with table format
          * Task | Marked As | Verified As | Evidence
          * **Highlight falsely marked complete tasks prominently**
          * Summary: X of Y tasks verified, Z questionable, W false completions
        - **Zero-Mock Enforcement**:
          * Include complete zero-mock checklist with table format
          * Check Type | File:Line | Status | Details
          * **Highlight any violations prominently**
          * Summary: ZERO-MOCK STATUS: PASS/FAIL - X violations
        - **Orphaned Files Enforcement**:
          * Include complete orphan checklist with table format
          * File Path | Issue Type | Severity | Suggested Location
          * **Highlight any violations prominently**
          * Summary: ORPHAN STATUS: PASS/FAIL - X violations
        - Test Coverage and Gaps
        - Architectural Alignment
        - Security Notes
        - Best-Practices and References (with links)
        - Action Items:
          * CRITICAL: Format with checkboxes for tracking resolution
          * Code changes required: `- [ ] [Severity] Description [file: path:line]`
          * Advisory notes: `- Note: Description (no action required)`
          * Group by type: "Code Changes Required" and "Advisory Notes"
      </action>
      <action>Add a Change Log entry with date, version bump if applicable, and description: "Senior Developer Review notes appended".</action>
      <action>If {{update_status_on_result}} is true: update Status to {{status_on_approve}} when approved; to {{status_on_changes_requested}} when changes requested; otherwise leave unchanged.</action>
      <action>Save the story file.</action>

      <critical>MUST include the complete validation checklists - this is the evidence that systematic review was performed</critical>
    </check>
  </step>

  <step n="8" goal="Update sprint status based on review outcome" tag="sprint-status">
    <check if="ad_hoc_review_mode == true">
      <action>Skip sprint status update (no story context)</action>
      <output>📋 Ad-hoc review complete - no sprint status to update</output>
    </check>

    <check if="ad_hoc_review_mode != true">
      <action>Determine target status based on review outcome:
        - If {{outcome}} == "Approve" → target_status = "done"
        - If {{outcome}} == "Changes Requested" → target_status = "in-progress"
        - If {{outcome}} == "Blocked" → target_status = "review" (stay in review)
      </action>

      <action>Load the FULL file: {{output_folder}}/sprint-status.yaml</action>
      <action>Read all development_status entries to find {{story_key}}</action>
      <action>Verify current status is "review" (expected previous state)</action>
      <action>Update development_status[{{story_key}}] = {{target_status}}</action>
      <action>Save file, preserving ALL comments and structure including STATUS DEFINITIONS</action>

      <check if="update successful">
        <output>✅ Sprint status updated: review → {{target_status}}</output>
      </check>

      <check if="story key not found">
        <output>⚠️ Could not update sprint-status: {{story_key}} not found

Review was saved to story file, but sprint-status.yaml may be out of sync.
        </output>
      </check>
    </check>
  </step>

  <step n="9" goal="Persist action items to tasks/backlog/epic">
    <check if="ad_hoc_review_mode == true">
      <action>All action items are included in the standalone review report</action>
      <ask if="action items exist">Would you like me to create tracking items for these action items? (backlog/tasks)</ask>
      <action if="user confirms">
        If {{backlog_file}} does not exist, copy {installed_path}/backlog_template.md to {{backlog_file}} location.
        Append a row per action item with Date={{date}}, Story="Ad-Hoc Review", Epic="N/A", Type, Severity, Owner (or "TBD"), Status="Open", Notes with file refs and context.
      </action>
    </check>

    <check if="ad_hoc_review_mode != true">
      <action>Normalize Action Items into a structured list: description, severity (High/Med/Low), type (Bug/TechDebt/Enhancement), suggested owner (if known), related AC/file references.</action>
      <ask if="action items exist and 'story_tasks' in {{persist_targets}}">Add {{action_item_count}} follow-up items to story Tasks/Subtasks?</ask>
      <action if="user confirms or no ask needed">
        Append under the story's "Tasks / Subtasks" a new subsection titled "Review Follow-ups (AI)", adding each item as an unchecked checkbox in imperative form, prefixed with "[AI-Review]" and severity. Example: "- [ ] [AI-Review][High] Add input validation on server route /api/x (AC #2)".
      </action>
      <action>
        If {{backlog_file}} does not exist, copy {installed_path}/backlog_template.md to {{backlog_file}} location.
        Append a row per action item with Date={{date}}, Story={{epic_num}}.{{story_num}}, Epic={{epic_num}}, Type, Severity, Owner (or "TBD"), Status="Open", Notes with short context and file refs.
      </action>
      <action>
        If an epic Tech Spec was found: open it and create (if missing) a section titled "{{epic_followups_section_title}}". Append a bullet list of action items scoped to this epic with references back to Story {{epic_num}}.{{story_num}}.
      </action>
      <action>Save modified files.</action>
      <action>Optionally invoke tests or linters to verify quick fixes if any were applied as part of review (requires user approval for any dependency changes).</action>
    </check>
  </step>

  <step n="10" goal="Validation and completion">
    <invoke-task>Run validation checklist at {installed_path}/checklist.md using {project-root}/.bmad/core/tasks/validate-workflow.xml</invoke-task>
    <action>Report workflow completion.</action>

    <check if="ad_hoc_review_mode == true">
      <output>**✅ Ad-Hoc Code Review Complete, {user_name}!**

**Review Details:**
- Files Reviewed: {{review_files}}
- Review Focus: {{review_focus}}
- Review Outcome: {{outcome}}
- Action Items: {{action_item_count}}
- Review Report: {{output_folder}}/code-review-{{date}}.md

**Next Steps:**
1. Review the detailed findings in the review report
2. If changes requested: Address action items in the code
3. If blocked: Resolve blockers before proceeding
4. Re-run review on updated code if needed
      </output>
    </check>

    <check if="ad_hoc_review_mode != true">
      <output>**✅ Story Review Complete, {user_name}!**

**Story Details:**
- Story: {{epic_num}}.{{story_num}}
- Story Key: {{story_key}}
- Review Outcome: {{outcome}}
- Sprint Status: {{target_status}}
- Action Items: {{action_item_count}}

**Next Steps:**
1. Review the Senior Developer Review notes appended to story
2. If approved: Story is marked done, continue with next story
3. If changes requested: Address action items and re-run `dev-story`
4. If blocked: Resolve blockers before proceeding
      </output>
    </check>
  </step>

</workflow>
````
