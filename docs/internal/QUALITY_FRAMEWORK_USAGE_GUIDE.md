# Quality Framework Usage Guide

**Document Version**: 1.0
**Created**: 2025-10-15
**For**: Epic 11 Documentation Stories (11.2, 11.3, 11.4, 11.5)
**Status**: Active

---

## Quick Start

This guide shows you how to use the Documentation Quality Framework created in Story 11.1 to produce production-quality documentation for RustyBT.

**Target Audience**: Dev agents and developers working on Epic 11 documentation stories

**Prerequisites**:
- Story 11.1 completed
- Quality framework components in place
- Story assignment for 11.2, 11.3, or 11.4

---

## Framework Components Overview

The quality framework consists of:

1. **Quality Standards** - What "good" documentation looks like
2. **Creation Checklist** - Pre-flight verification before starting
3. **Validation Checklist** - Comprehensive validation before completion
4. **Automation Scripts** - Tools for API/example verification
5. **Artifact Infrastructure** - Storage for quality evidence
6. **Expert Review Process** - External validation workflow

**All components are mandatory for Epic 11 stories.**

---

## Complete Workflow (Start to Finish)

### Phase 0: Story Assignment & Preparation

**When**: Immediately after story assignment

**Actions**:
1. Read assigned story file completely
2. Note all acceptance criteria
3. Identify story-specific requirements
4. Estimate time and resources needed

**Duration**: 30-60 minutes

---

### Phase 1: Pre-Flight Checklist (BLOCKING)

**When**: Before writing any documentation

**Actions**:

1. **Load Pre-Flight Checklist**
   ```bash
   # View the checklist
   cat docs/internal/DOCUMENTATION_CREATION_CHECKLIST.md
   ```

2. **Complete All Sections**
   - Section 1: Framework Knowledge Verification
   - Section 2: Source Code Analysis
   - Section 3: Testing Preparation
   - Section 4: Reference Material Review
   - Section 5: Quality Framework Understanding
   - Section 6: Epic 11 Course Change Context
   - Section 7: Resource Availability Assessment

3. **Create Pre-Flight Artifact**
   ```bash
   # Copy template
   cp docs/internal/DOCUMENTATION_CREATION_CHECKLIST.md \
      docs/internal/story-artifacts/pre-flight-checklists/{story-id}-pre-flight.md

   # Example for Story 11.2
   cp docs/internal/DOCUMENTATION_CREATION_CHECKLIST.md \
      docs/internal/story-artifacts/pre-flight-checklists/11.2-pre-flight.md
   ```

4. **Fill Out Checklist**
   - Replace `{story-number}` with actual story ID
   - Check all boxes honestly
   - Fill in the "I certify" statement
   - Sign with your name and date

5. **Reference in Story File**
   Update story Dev Agent Record section:
   ```markdown
   ### Pre-Flight Checklist
   - Location: `docs/internal/story-artifacts/pre-flight-checklists/11.2-pre-flight.md`
   - Status: Complete
   - Date: 2025-10-15
   ```

**Duration**: 1-2 hours

**CRITICAL**: Cannot proceed to Phase 2 without completing pre-flight checklist!

---

### Phase 2: Documentation Creation

**When**: After pre-flight checklist approved

**Actions**:

1. **Review Quality Standards**
   ```bash
   cat docs/internal/DOCUMENTATION_QUALITY_STANDARDS.md
   ```
   Focus on:
   - Core Principle #1: Executable Truth
   - API Reference Standards
   - Code Example Standards

2. **Follow the Six Core Principles**
   -  Executable Truth: All examples must run
   -  Production Quality: No placeholders or simplifications
   -  Comprehensive Coverage: All public APIs documented
   -  Usage-Driven: Show how to use, not just what exists
   -  Validated Accuracy: Test everything
   -  Safety First: Security and best practices

3. **Write Documentation**
   - Start with overview/README
   - Document each API module
   - Include complete, executable examples
   - Cross-reference related APIs
   - Add troubleshooting sections

4. **Test Continuously**
   Run verification script frequently:
   ```bash
   # Test specific module as you work
   python3 scripts/verify_documented_apis.py --docs-path docs/api/your-module

   # Full suite test
   python3 scripts/verify_documented_apis.py
   ```

**Duration**: Varies by story (8-20 hours)

**Tips**:
- Test examples as you write them
- Use real data, not mock values
- Reference actual code in rustybt package
- Run verification script after each section

---

### Phase 3: Validation (BLOCKING)

**When**: After documentation complete, before marking story done

**Actions**:

1. **Run Full Automated Validation**
   ```bash
   # Full validation with example execution
   python3 scripts/verify_documented_apis.py > validation-output.txt 2>&1

   # Review results
   cat validation-output.txt

   # Check JSON report for details
   cat scripts/api_verification_report.json | jq '.summary'
   ```

2. **Verify Quality Gates**
   - API Verification Rate: 100% required
   - Example Execution Rate: >90% required
   - Usage Pattern Issues: <10% acceptable

3. **Load Validation Checklist**
   ```bash
   cat docs/internal/DOCUMENTATION_VALIDATION_CHECKLIST.md
   ```

4. **Complete Validation Checklist**
   - Section 1: API Accuracy Validation (10 items)
   - Section 2: Code Example Validation (9 items)
   - Section 3: Usage Pattern Validation (8 items)
   - Section 4: Cross-Reference Validation (5 items)
   - Section 5: Style and Clarity (6 items)
   - Section 6: Completeness Check (7 items)
   - Section 7: Quality Framework Compliance (6 items)
   - Section 8: Expert Review Preparation (5 items)
   - Section 9: Epic 11 Compliance (5 items)
   - Section 10: Final Verification and Sign-Off (9 items)

5. **Create Validation Artifact**
   ```bash
   # Copy template
   cp docs/internal/DOCUMENTATION_VALIDATION_CHECKLIST.md \
      docs/internal/story-artifacts/validation-results/{story-id}-validation.md

   # Example for Story 11.2
   cp docs/internal/DOCUMENTATION_VALIDATION_CHECKLIST.md \
      docs/internal/story-artifacts/validation-results/11.2-validation.md
   ```

6. **Fill Out Validation Checklist**
   - Check all boxes honestly
   - Document any deviations with justification
   - Include validation date
   - Attach automation results
   - Sign as author

7. **Save Test Results**
   ```bash
   # Create test results directory
   mkdir -p docs/internal/story-artifacts/{story-id}-test-results

   # Save verification results
   python3 scripts/verify_documented_apis.py > \
      docs/internal/story-artifacts/{story-id}-test-results/api-verification-$(date +%Y-%m-%d).txt 2>&1

   # Copy JSON report
   cp scripts/api_verification_report.json \
      docs/internal/story-artifacts/{story-id}-test-results/
   ```

8. **Reference in Story File**
   ```markdown
   ### Validation Results
   - Location: `docs/internal/story-artifacts/validation-results/11.2-validation.md`
   - Test Results: `docs/internal/story-artifacts/11.2-test-results/`
   - API Verification Rate: 100%
   - Example Pass Rate: 95%
   - Status: PASSED
   - Date: 2025-10-16
   ```

**Duration**: 2-4 hours

**CRITICAL**: Cannot proceed to expert review without passing validation!

---

### Phase 4: Expert Review (BLOCKING)

**When**: After validation passes

**Actions**:

1. **Review Expert Review Process**
   ```bash
   cat docs/internal/EXPERT_REVIEW_PROCESS.md
   ```

2. **Schedule Expert Review**
   - Contact expert with 1 week advance notice
   - Provide review package:
     - Documentation location
     - Pre-flight checklist
     - Validation results
     - Test results
   - Propose 2-3 time slots
   - Confirm 24 hours before

3. **Prepare for Review**
   - Ensure all documentation is final
   - Have test environment ready
   - Prepare to demonstrate examples
   - Review validation results yourself

4. **Conduct Review Session**
   - Expert leads review (1-3 hours)
   - Expert uses review template
   - Document all findings
   - Note recommendations
   - Get approval decision

5. **Handle Expert Feedback**
   - **If Approved**: Proceed to artifact filing
   - **If Approved with Conditions**: Fix minor issues, no re-review
   - **If Needs Revision**: Fix all issues, schedule follow-up
   - **If Rejected**: Major rework, restart from Phase 2

6. **Create Expert Review Artifact**
   Expert fills out:
   ```
   docs/internal/story-artifacts/expert-reviews/{story-id}-expert-review.md
   ```

   Based on template:
   ```
   docs/internal/story-artifacts/templates/expert-review-template.md
   ```

7. **Reference in Story File**
   ```markdown
   ### Expert Review
   - Location: `docs/internal/story-artifacts/expert-reviews/11.2-expert-review.md`
   - Reviewer: [Expert Name]
   - Review Date: 2025-10-17
   - Status: APPROVED
   - Conditions: [None / See artifact]
   ```

**Duration**: 1-3 hours (review session) + time for any fixes

**CRITICAL**: Cannot mark story complete without expert approval!

---

### Phase 5: Story Completion

**When**: After expert approval obtained

**Actions**:

1. **Verify All Artifacts Exist**
   ```bash
   # Check artifacts
   ls -l docs/internal/story-artifacts/pre-flight-checklists/{story-id}*
   ls -l docs/internal/story-artifacts/validation-results/{story-id}*
   ls -l docs/internal/story-artifacts/expert-reviews/{story-id}*
   ls -l docs/internal/story-artifacts/{story-id}-test-results/
   ```

2. **Update Story File**
   - Mark all tasks complete with [x]
   - Update File List section with all created/modified files
   - Complete Dev Agent Record section
   - Add Completion Notes
   - Update Change Log
   - Set Status to "Ready for Review"

3. **Final Quality Check**
   - All acceptance criteria met
   - All story tasks checked off
   - All artifacts referenced in story file
   - Expert approval obtained
   - No open critical issues

4. **Mark Story Complete**
   - Update story status
   - Notify PM/QA
   - Handoff to next story (if applicable)

**Duration**: 30-60 minutes

---

## Story-Specific Guidance

### Story 11.2: Data Management Documentation

**Focus Areas**:
- Data adapters (CCXT, yfinance, CSV)
- Data catalog and caching
- Pipeline system
- Bar readers and data portal

**Special Requirements**:
- All adapters must have functional examples
- Caching behavior must be demonstrated
- Pipeline examples must show real data flow

**Estimated Effort**: 16-24 hours

---

### Story 11.3: Order & Portfolio Management Documentation

**Focus Areas**:
- Order types and execution
- Portfolio management
- Multi-strategy coordination
- Transaction cost models

**Special Requirements**:
- AC #5: Order type verification with ALL 7 order types
- Each order type needs working example
- Transaction cost examples must show actual calculations

**Estimated Effort**: 16-24 hours

---

### Story 11.4: Optimization & Analytics Documentation

**Focus Areas**:
- Optimization algorithms
- Walk-forward optimization
- Monte Carlo simulation
- Analytics and attribution

**Special Requirements**:
- AC #5: Technical accuracy checklist
- All algorithms must have runnable examples
- Performance benchmarks must be accurate

**Estimated Effort**: 16-24 hours

---

## Common Pitfalls and How to Avoid Them

### Pitfall #1: Skipping Pre-Flight Checklist
**Problem**: Starting documentation without understanding requirements
**Solution**: Always complete pre-flight checklist first, even if it seems tedious

### Pitfall #2: Writing Incomplete Examples
**Problem**: Examples with `...` or placeholders that don't execute
**Solution**: Every example must be copy-pasteable and runnable

### Pitfall #3: Not Testing Continuously
**Problem**: Discovering issues late in the process
**Solution**: Run verification script after each section

### Pitfall #4: Ignoring Usage Patterns
**Problem**: Examples that are technically correct but demonstrate anti-patterns
**Solution**: Follow coding standards, show best practices

### Pitfall #5: Rushing Validation
**Problem**: Missing issues that expert review will find
**Solution**: Treat validation as seriously as creation

### Pitfall #6: Inadequate Expert Review Preparation
**Problem**: Wasting expert time with incomplete work
**Solution**: Only request review after validation passes

---

## Quality Gates Checklist

Before requesting expert review, verify:

- [ ] Pre-flight checklist complete and filed
- [ ] All acceptance criteria addressed
- [ ] API verification rate = 100%
- [ ] Example pass rate >90%
- [ ] Usage pattern issues <10%
- [ ] Validation checklist complete and filed
- [ ] Test results saved and referenced
- [ ] All cross-references verified
- [ ] No hardcoded values or placeholders
- [ ] All examples demonstrate real usage

---

## Automation Commands Reference

### Basic Verification
```bash
# Verify documentation (with example execution)
python3 scripts/verify_documented_apis.py

# Verify without running examples (faster)
python3 scripts/verify_documented_apis.py --no-examples

# Verify specific module
python3 scripts/verify_documented_apis.py --docs-path docs/api/data-management
```

### Results Analysis
```bash
# View summary
python3 scripts/verify_documented_apis.py | grep -A 20 "VERIFICATION SUMMARY"

# Check JSON report
cat scripts/api_verification_report.json | jq '.summary'

# List failed examples
cat scripts/api_verification_report.json | jq '.failed_examples[]'

# List fabricated APIs (should be empty!)
cat scripts/api_verification_report.json | jq '.fabricated_apis[]'
```

### Artifact Management
```bash
# Create pre-flight checklist
cp docs/internal/DOCUMENTATION_CREATION_CHECKLIST.md \
   docs/internal/story-artifacts/pre-flight-checklists/{story-id}-pre-flight.md

# Create validation checklist
cp docs/internal/DOCUMENTATION_VALIDATION_CHECKLIST.md \
   docs/internal/story-artifacts/validation-results/{story-id}-validation.md

# Create test results directory
mkdir -p docs/internal/story-artifacts/{story-id}-test-results

# Save test results
python3 scripts/verify_documented_apis.py > \
   docs/internal/story-artifacts/{story-id}-test-results/verification-$(date +%Y-%m-%d).txt 2>&1
```

---

## Quick Reference: File Locations

| Document | Location |
|----------|----------|
| Quality Standards | `docs/internal/DOCUMENTATION_QUALITY_STANDARDS.md` |
| Creation Checklist | `docs/internal/DOCUMENTATION_CREATION_CHECKLIST.md` |
| Validation Checklist | `docs/internal/DOCUMENTATION_VALIDATION_CHECKLIST.md` |
| Expert Review Process | `docs/internal/EXPERT_REVIEW_PROCESS.md` |
| Verification Script | `scripts/verify_documented_apis.py` |
| Artifact Storage | `docs/internal/story-artifacts/` |
| Templates | `docs/internal/story-artifacts/templates/` |

---

## Success Metrics

Track these metrics for your documentation work:

- **API Verification Rate**: Target 100%
- **Example Execution Rate**: Target >95%
- **Usage Pattern Quality**: Target <5% issues
- **Validation Pass Rate**: Target first-time pass
- **Expert Review Approval**: Target approved or approved-with-conditions
- **Rework Cycles**: Target d1 revision after expert review

---

## Getting Help

### Documentation Questions
1. Review quality standards document
2. Check story acceptance criteria
3. Look at completed Epic 10 examples (in archive) for reference
4. Contact PM Agent (John)

### Technical Questions
1. Review source code
2. Test in interactive Python session
3. Check existing examples
4. Contact expert or senior engineer

### Process Questions
1. Review this usage guide
2. Check expert review process document
3. Review story artifacts README
4. Contact PM Agent (John)

---

## Appendix: Complete Example Workflow

Here's a complete example for Story 11.2:

```bash
# === PHASE 1: PRE-FLIGHT ===

# 1. Create pre-flight checklist
cp docs/internal/DOCUMENTATION_CREATION_CHECKLIST.md \
   docs/internal/story-artifacts/pre-flight-checklists/11.2-pre-flight.md

# 2. Edit and complete checklist
# (Fill out all sections, sign)

# === PHASE 2: CREATE DOCUMENTATION ===

# 3. Write documentation in docs/api/data-management/
# (Create README, adapter docs, catalog docs, etc.)

# 4. Test continuously
python3 scripts/verify_documented_apis.py --docs-path docs/api/data-management

# === PHASE 3: VALIDATION ===

# 5. Run full validation
python3 scripts/verify_documented_apis.py

# 6. Create validation checklist
cp docs/internal/DOCUMENTATION_VALIDATION_CHECKLIST.md \
   docs/internal/story-artifacts/validation-results/11.2-validation.md

# 7. Complete validation checklist
# (Check all boxes, attach results)

# 8. Save test results
mkdir -p docs/internal/story-artifacts/11.2-test-results
python3 scripts/verify_documented_apis.py > \
   docs/internal/story-artifacts/11.2-test-results/verification-2025-10-16.txt 2>&1

# === PHASE 4: EXPERT REVIEW ===

# 9. Schedule expert review
# (Email expert, provide review package)

# 10. Conduct review session
# (Expert completes review template)

# 11. Expert creates review artifact
# docs/internal/story-artifacts/expert-reviews/11.2-expert-review.md

# === PHASE 5: COMPLETION ===

# 12. Update story file
# (Mark tasks complete, reference artifacts, update status)

# 13. Verify all artifacts
ls -l docs/internal/story-artifacts/pre-flight-checklists/11.2*
ls -l docs/internal/story-artifacts/validation-results/11.2*
ls -l docs/internal/story-artifacts/expert-reviews/11.2*
ls -l docs/internal/story-artifacts/11.2-test-results/

# 14. Mark story complete
# (Update story status to "Ready for Review")
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-15 | Initial creation for Epic 11 | James (Dev Agent) |

---

**Questions?** Review the framework documents or contact PM Agent (John).

**Good luck with your documentation work!** =
