> Planning context adapted from the supplied blueprint. This describes future product scope, not shipped features. See [current roadmap](../ROADMAP.md) and [implemented architecture](../ARCHITECTURE.md). Referenced versions, licenses, and community statistics are historical planning notes and must be checked before reuse.

# Verified resources (accessed 2026-11-25)

References used to build StudyBuddy's original design; inspect current licenses and versions before incorporating any code/data.

## Large existing projects
- DeepTutor (lifelong personalized tutoring, mastery paths, quizzes, document grounding): https://github.com/HKUDS/DeepTutor (Apache 2.0; ~62.7k stars at inspection)
- Khoj (local-first knowledge assistant): https://github.com/khoj-ai/khoj (AGPL-3.0; ~38.2k stars; **do not directly copy AGPL code into an MIT project without assessing obligations**)
- Anki: https://github.com/ankitects/anki (~33k stars; inspect licensing independently)
- ActivityWatch (local time tracking, REST API): https://github.com/ActivityWatch/activitywatch (~19.8k stars); https://docs.activitywatch.net/en/latest/api.html
- Word Atlas / 词光: https://github.com/designfuchen/word-atlas (~5.3k stars, code MIT, data + illustrations + word recordings CC BY 4.0 with attribution; hosted site may differ)
- Obsidian Spaced Repetition: https://github.com/st3v3nmw/obsidian-spaced-repetition (MIT; ~2.6k stars)
- OpenTutor: https://github.com/zijinz456/OpenTutor (self-hosted adaptive learning; ~192 stars)
- Agent tutor for Obsidian: https://github.com/Mohamed-El-Sharqawy/agent-tutor

## Interfaces and algorithms
- Obsidian official CLI: https://obsidian.md/help/cli
- Obsidian community Local REST API: https://community.obsidian.md/plugins/obsidian-local-rest-api
- Obsidian Headless beta: https://obsidian.md/help/headless
- FSRS TypeScript: https://github.com/open-spaced-repetition/ts-fsrs (MIT)
- AnkiConnect API: https://github.com/FooSoft/anki-connect
- ActivityWatch API: https://docs.activitywatch.net/en/latest/api.html
- ActivityWatch watcher privacy filtering: https://github.com/ActivityWatch/aw-watcher-window
- OpenAI custom MCP availability: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt (account/plan dependent; do not make MVP depend on a specific ChatGPT entitlement)

## Vocabulary sources
- Word Atlas licensed IELTS vocabulary: https://github.com/designfuchen/word-atlas
- English word frequency: https://github.com/rspeer/wordfreq (package Apache 2.0, included datasets may be CC BY-SA 4.0: observe specific obligations)
- Tech term definitions: https://github.com/do-community/developer-glossary (MIT; small curated glossary, not comprehensive)
- English for developers resource index: https://github.com/ksushbush/awesome-english-for-developers
- Engineering English lessons: https://github.com/xiaobinqin/english-mastery-plan
- Developer/technical interview phrase examples: https://github.com/yexia553/developer-english-phrases (check license before reuse)

## Educational research
- Retrieval + spacing evidence: https://www.nature.com/articles/s44159-022-00089-1
- Learning-styles matching claim not sufficiently supported: https://digitalcommons.usf.edu/psy_facpub/1765/
- 2025 reanalysis: https://link.springer.com/article/10.1007/s10648-025-10002-w

## Community signal (anecdotes, not controlled research)
- Obsidian revisit issue: https://www.reddit.com/r/ObsidianMD/comments/1w6jyr3/how_often_do_you_actually_revisit_your_obsidian/
- Review metadata vs Anki: https://www.reddit.com/r/ObsidianMD/comments/1w8ik7f/i_stopped_reviewing_notes_in_obsidian_and_moved/
- Low-overhead task tracking: https://www.reddit.com/r/ADHD_Programmers/comments/1tzmzq8/looking_for_assistance_on_managing_tasks_and_time/

## Existing dictionary integration (found during follow-up research)
- Eudic/欧路 official OpenAPI entry point (authentication likely required for some detailed docs): https://my.eudic.net/OpenAPI/Doc_Index
- Eudic official product update notes say desktop versions can export vocabulary to CSV/Anki: https://www.eudic.net/v4/en/app/history?appkey=eusoft_eudic_en
- Example third-party client (study its API use, not authentication token storage practices): https://github.com/eMUQI/eudic-maimemo-sync

**Recommendation:** users can keep looking up words in Eudic; add an opt-in `EudicVocabularySource` supporting documented API sync or CSV import, preserving original word-book names and timestamps where available. Do not automatically sync all dictionary content or leak credentials.
