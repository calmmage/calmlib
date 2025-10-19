---
type: project
status: idea/draft
tags:
  - coding
---
## Description

## Actions
```dataview
TABLE
WHERE type = "action" or type = "artifact"
WHERE contains(project, this.file.link)
SORT created DESC
```
