---
post_title: "Refactor Template"
author1: "xNetVN Inc."
post_slug: "docs-en-template-refactor"
microsoft_alias: ""
featured_image: ""
categories:
  - templates
tags:
  - refactor
ai_note: "AI-assisted"
summary: "Refactor request template."
post_date: "2026-02-03"
---

## 1. General information

- **Project name:** [Project name]
- **Module/Functionality to refactor:** [e.g., User management, Payment processing, Product API...]
- **Codebase link (repo):** [GitHub/GitLab/Bitbucket link or internal path]
- **Requester:** [Name, Email/Phone/Slack...]

---

## 2. Scope

- **Parts/functions/classes/features to refactor:**  
  - [ ] [Specific function/class/file/module name]  
  - [ ] [Short description of the functionality]

- **Reasons for refactoring:**  
  - [ ] Poor performance (Performance)
  - [ ] Bug-prone / high defect density
  - [ ] Hard to test (Testability)
  - [ ] Hard to maintain/scale (Maintainability/Scalability)
  - [ ] Code standardization / quality improvement (Code quality)
  - [ ] Violates coding conventions/standards (Coding convention)
  - [ ] Security/compliance concerns (Security/Compliance)
  - [ ] Reliability issues
  - [ ] Preparing for integration/new features
  - [ ] Technical debt
  - [ ] Other: [Describe]
  
- **Evidence / issue references:**  
  - [ ] Links to test cases, bug reports, logs, screenshots, detailed repro steps...

---

## 3. Detailed description

- **Current state:**  
  _Briefly describe the current issues, for example:_
  > e.g., Function is too slow with large data; hard to read and change; prone to errors when integrating new modules...

- **Real-world impact:**  
  > e.g., Slows releases, increases production risk, blocks new features, customers complain about performance/stability...

- **Expected outcome after refactor:**  
  _Describe the target, for example:_
  > e.g., Processing time < 1s for 1M records; clear code with documentation; easier feature additions; improved security...

---

## 4. Expected results & reporting

- **Expected results:**  
  - [ ] Clean, readable, standardized refactored code (with comments/docs)
  - [ ] Full testing coverage, all existing tests pass, add tests if missing (unit/integration)
  - [ ] Code is readable and follows coding standards
  - [ ] Fix recorded issues and reduce potential defects
  - [ ] Optimize performance / meet security standards
  - [ ] Before/after comparison report (performance, test coverage, issues/warnings, security)
  - [ ] Documentation describing changes, usage guidance, and re-test steps
  - [ ] Pull request includes review checklist and detailed change summary

---

## 5. Timeline & priority

- **Desired deadline:** [dd/mm/yyyy]
- **Priority:** [High/Medium/Low]
- **Impact if not executed:**  
  _Example: Impacts project schedule, increases defect risk, blocks scaling..._

---

## 6. Additional information (Optional)

- Reference documents, coding standards, internal guidelines:
  - [Link to coding standards]
  - [Review requirements, CI/CD, testing...]

---

## 7. Attachments (Optional)

- Screenshots of issues
- Log files, test data samples
- Videos showing reproduction steps

---

# 🛠️ **Guidance for the developer team**

- Clarify business goals with the requester when needed.
- Propose the most optimal refactor solution based on best practices and industry standards.
- Ensure thorough reviews with a pre-merge checklist.
- Ensure all changes are thoroughly tested before merge.
- Propose improvements beyond scope if other critical issues are found.
- Ensure all changes can be rolled back if needed.
- Update progress, report results, and coordinate verification with the requester.

---

## 📬 **Contact & feedback process**

- **Requester:** [Name/Email/Slack...]
- **Communication workflow:**  
  - [ ] Share refactor plan (timeline, resources, estimates)
  - [ ] Agree on scope, goals, and schedule
  - [ ] Provide regular updates (daily/weekly)

---

**If you have questions, contact the requester directly for timely support.**
