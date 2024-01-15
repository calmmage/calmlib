Idea: make a simple tool that sets up my folder structure

MVP features list:
- [x] Create a folder structure
- [x] pick a root dir
- [ ] add ~/.calmlib/config.toml - for current config state, root dir and other
- [x] Presets, latest = current folder structure (latest added)
- [ ] Check if folder structure exists, if so, ask to overwrite
- [ ] add main cli.py using some modern python cli - typer, click, fire

Current folder structure:
- Discussion with GPT: 
code/structured/
code/chronological/
data/
tools/

# Extra features:
- [ ] sync

# Additional direction - cron job
Daily / weekly / monthly job to update softlinks / 
archive everything.. 
- 'latest' folder -> chronological / YYMM
- all new projects -> structured / unordered


# Related projects:
- Calmmage CLI Assistant - AI, Code Keeper, Hybrid vector store
- Calmmage Personal Assistant - tasks, calendar, reminders, notes, etc.
- Calmmage Save Manager - save bookmarks, notes, links, etc.
