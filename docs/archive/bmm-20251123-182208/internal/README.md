# RustyBT Internal Documentation

**Purpose**: This directory contains all internal development, process, and project management documentation.
**Audience**: RustyBT developers, contributors, and project maintainers
**Status**: Internal use only - excluded from user-facing documentation site

---

## What's in This Directory

### Architecture Documentation (`architecture/`)
- System architecture designs
- Component architecture specifications
- Epic-specific architecture documents
- Integration patterns and guidelines

### Product Requirements (`prd/`)
- Product requirements documents (PRDs)
- Epic definitions and specifications
- Feature specifications
- MVP scope definitions

### Stories (`stories/`)
- User story specifications
- Completed story records
- Story templates and examples
- Implementation notes

### QA & Testing (`qa/`)
- QA assessment reports
- Test execution results
- Sprint change proposals
- Remediation summaries
- Quality gate records

### Development (`development/`)
- CI/CD pipeline documentation
- Rust setup and configuration
- Development environment guides
- Build and deployment notes

### Testing (`testing/`)
- Testing strategy documentation
- Property-based testing guides
- Test framework documentation

### Pull Requests (`pr/`)
- PR documentation and analysis
- Blocking issue documentation
- Solution proposals

### Experiments (`experiments/`)
- Research and experimental code
- Proof of concepts
- Comparison studies
- Investigation notes

---

## Documentation Organization Philosophy

### Internal vs External Documentation

**Internal Documentation** (this directory):
- **Audience**: Developers, contributors, maintainers
- **Purpose**: Development process, architecture decisions, project management
- **Examples**: PRDs, stories, QA reports, architecture docs
- **Visibility**: Excluded from mkdocs build (not on documentation site)

**External Documentation** (`docs/` root):
- **Audience**: RustyBT users, integration developers
- **Purpose**: How to use the framework, API reference, guides
- **Examples**: Getting started, guides, API reference, examples
- **Visibility**: Included in mkdocs build (public documentation site)

### Why This Separation Matters

1. **Clarity**: Users aren't overwhelmed with internal process documents
2. **Simplicity**: mkdocs configuration is simpler (exclude just `internal/`)
3. **Maintainability**: Clear boundaries for different documentation types
4. **Professionalism**: User-facing docs remain clean and focused

---

## Directory Structure

```
docs/internal/
├── README.md                 # This file
├── architecture/             # System and component architecture
├── prd/                      # Product requirements and epic definitions
├── stories/                  # User stories and implementation records
│   ├── completed/           # Completed story archives
│   └── *.md                 # Active/pending stories
├── qa/                       # QA reports, assessments, change proposals
├── development/              # Development environment and CI/CD
├── testing/                  # Testing strategy and framework docs
├── pr/                       # Pull request documentation
└── experiments/              # Research and experimental work
```

---

## Key Internal Documents

### Epic 11 (Current)
- **Epic Definition**: `prd/epic-11-documentation-quality-framework-and-epic10-redo.md`
- **Sprint Change Proposal**: `qa/SPRINT_CHANGE_PROPOSAL_EPIC10_COMPLETE_REDO.md`
- **Quality Standards**: `DOCUMENTATION_QUALITY_STANDARDS.md` (to be created)
- **Creation Checklist**: `DOCUMENTATION_CREATION_CHECKLIST.md` (to be created)
- **Validation Checklist**: `DOCUMENTATION_VALIDATION_CHECKLIST.md` (to be created)

### Epic 10 (Superseded)
- **Epic Definition**: `prd/epic-10-comprehensive-framework-documentation.md`
- **Architecture**: `architecture/epic-10-documentation-architecture.md`
- **Remediation**: `qa/EPIC10_REMEDIATION_SUMMARY.md`
- **Story 10.X1**: `stories/10.X1.audit-and-remediate-epic10-fabricated-apis.md`

### Archived Documentation
- **Epic 10 v1 Archive**: `../archive/v1-epic10-2025-10-15/`

---

## How to Use This Directory

### For Developers
- Reference architecture documents before implementing features
- Read PRD and epic definitions to understand requirements
- Check story specifications for acceptance criteria
- Review QA reports for quality standards
- Consult coding standards and patterns

### For Contributors
- Read architecture documents to understand system design
- Review completed stories for implementation examples
- Check development guides for environment setup
- Follow testing documentation for test strategy

### For Project Managers
- Create new epics in `prd/`
- Create new stories in `stories/`
- Document change proposals in `qa/`
- Track epic and story progress
- Manage quality gates and reviews

---

## Adding New Internal Documentation

### Creating New Epics
1. Create epic document in `prd/epic-{n}-{name}.md`
2. Create architecture document in `architecture/epic-{n}-{name}-architecture.md` (if needed)
3. Reference from related stories

### Creating New Stories
1. Create story in `stories/{epic}.{story}.{name}.md`
2. Follow story template format
3. Move to `stories/completed/` when done

### Creating QA Reports
1. Create assessment in `qa/assessments/{name}.md`
2. Create change proposals in `qa/SPRINT_CHANGE_PROPOSAL_{NAME}.md`
3. Document remediation in `qa/{NAME}_REMEDIATION_SUMMARY.md`

---

## Maintenance Notes

**Last Reorganization**: 2025-10-15 (Epic 11 Story 11.1)
**Reorganization Reason**: Separate internal and external documentation
**Previous Location**: Various locations in `docs/` root
**Current Structure**: Consolidated in `docs/internal/`

---

**Maintained By**: RustyBT Project Team
**Questions**: See `../about/contributing.md` for contribution guidelines
