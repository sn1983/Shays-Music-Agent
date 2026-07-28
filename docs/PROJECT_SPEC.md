# PROJECT_SPEC.md

# Music Nostalgia AI Agent

Version: 1.0

---

# Vision

לבנות סוכן AI אוטונומי המתמחה במוזיקת Pop ו-Rock מהעשורים:

- 90's
- 2000's
- 2010's
- 2020's

מטרת הסוכן היא לשלוח באופן אוטומטי המלצות מוזיקה איכותיות, מעניינות ונוסטלגיות לערוץ Telegram.

בעתיד הסוכן יוכל גם לפרסם אוטומטית בפייסבוק, בלוג, אתר אינטרנט ורשתות נוספות.

---

# Main Goals

הסוכן צריך להיות מסוגל:

- לבחור שיר אחד או יותר בכל יום.
- לבחור רק שירים איכותיים.
- לא לחזור על אותם שירים.
- לגוון בין אמנים.
- לגוון בין שנים.
- לגוון בין סגנונות.

הסוכן אינו מיועד לפרסום חדשות מוזיקה.

המטרה היא ליצור תוכן שאנשים אוהבים לקרוא.

---

# Audience

קהל יעד:

אנשים שאוהבים:

- Pop
- Pop Rock
- Soft Rock
- Dance Pop
- Euro Pop
- Adult Contemporary
- Alternative Rock

גילאים:

30–55

---

# Languages

Primary:

English Songs

Post language:

Hebrew

ייתכן שבעתיד:

English

---

# Daily Workflow

בכל יום:

1. לבחור שיר.
2. לאסוף מידע.
3. ליצור תקציר.
4. להוסיף עובדות מעניינות.
5. להוסיף קישורים.
6. לשלוח ל-Telegram.

---

# Song Selection Rules

אין לבחור:

- שירים שכבר פורסמו.
- יותר מדי שירים מאותו אמן.
- יותר מדי שירים מאותה שנה.

יש להעדיף:

- להיטים גדולים
- שירים שנשכחו
- One Hit Wonders
- Hidden Gems
- Album Tracks איכותיים
- Live Versions מיוחדות

---

# Decades Distribution

המטרה היא חלוקה מאוזנת.

לדוגמה:

90's → 30%

2000's → 30%

2010's → 20%

2020's → 20%

---

# Music Genres

מועדפים:

- Pop
- Pop Rock
- Rock
- Soft Rock
- Dance Pop
- Alternative Rock
- Synth Pop
- Indie Pop

לא לפרסם:

- Rap
- Metal
- Death Metal
- Hardcore
- Jazz
- Classical

אלא אם המשתמש יבקש אחרת.

---

# Information To Collect

עבור כל שיר:

Artist

Song

Album

Release Year

Genre

Songwriters

Producer

Album Cover

Spotify Link

YouTube Link

Apple Music Link (optional)

Wikipedia

Official Website

Lyrics Source

Streaming Popularity (optional)

---

# Interesting Facts

יש לאתר לפחות 3 עובדות מעניינות.

לדוגמה:

- מה היו ההשראות לכתיבת השיר.
- האם השיר זכה בפרסים.
- האם הגיע למקום ראשון.
- האם הופיע בסרט.
- האם עבר חידוש.
- האם קיים סיפור מעניין מאחורי ההקלטות.

---

# Hebrew Summary

הסוכן ייצור תקציר קצר בעברית.

אורך:

80–150 מילים.

הכתיבה צריכה להיות:

- זורמת
- מעניינת
- קלילה
- לא ויקיפדית
- לא רובוטית

---

# Telegram Message Template

🎵 שיר היום

🎤 Artist:

📀 Album:

📅 Year:

⭐ Genre:

---

תקציר

---

💡 הידעת?

Fact 1

Fact 2

Fact 3

---

🎧 Spotify

▶ YouTube

🌍 Wikipedia

---

מה דעתכם על השיר?

---

# AI Writing Style

לכתוב כאילו מדובר בשדרן רדיו.

לא:

"רשימת נתונים"

כן:

סיפור.

המטרה היא לגרום לקורא להקשיב לשיר.

---

# Avoid Hallucinations

אם מידע אינו קיים:

אין להמציא.

עדיף להשמיט.

---

# Sources Priority

1 Official Website

2 Spotify

3 Wikipedia

4 Billboard

5 Rolling Stone

6 AllMusic

7 Discogs

---

# Duplicate Protection

יש לשמור Database.

עבור כל שיר:

Song ID

Artist

Date Published

Telegram Message ID

Facebook Post ID

Views

Likes

Comments

---

# Scheduling

ברירת מחדל:

20:00

Timezone:

Asia/Jerusalem

---

# Telegram Integration

הסוכן יפרסם אוטומטית באמצעות Telegram Bot API.

יכולות:

- Send Message
- Markdown Formatting
- Image
- Inline Buttons

---

# Future Facebook Integration

בעתיד:

Facebook Graph API

יכולות:

- Publish Post
- Publish Image
- Schedule Posts

---

# Future Website

בעתיד:

כל שיר יישמר באתר.

עמוד יכיל:

- Cover
- Summary
- Links
- Facts
- Comments
- Search

---

# Future AI Features

בעתיד:

- "ביום הזה במוזיקה"

- ימי הולדת של אמנים

- אלבום השבוע

- One Hit Wonder

- Forgotten Hit

- Cover vs Original

- Live Version

- Acoustic Version

- MTV Memories

- Top 10

- Polls

---

# Technologies

Python

Claude API

Telegram Bot API

SQLite

Later:

PostgreSQL

Redis

Docker

GitHub Actions

---

# Suggested Project Structure

music-agent/

docs/

PROJECT_SPEC.md

README.md

src/

scheduler/

telegram/

facebook/

database/

ai/

music/

storage/

logs/

config/

tests/

.env

requirements.txt

main.py

---

# Environment Variables

CLAUDE_API_KEY=

TELEGRAM_BOT_TOKEN=

TELEGRAM_CHAT_ID=

DATABASE_PATH=

TIMEZONE=Asia/Jerusalem

LOG_LEVEL=INFO

---

# Development Phases

Phase 1

✅ Telegram

✅ Claude

✅ SQLite

---

Phase 2

Facebook

---

Phase 3

Website

---

Phase 4

Analytics

---

Phase 5

Multi Agent System

---

# Claude Development Rules

Claude acts as a Senior Software Engineer.

Always:

- Write clean code.
- Use SOLID.
- Prefer modular architecture.
- Prefer Python typing.
- Write documentation.
- Write unit tests.
- Avoid duplicated code.
- Explain important decisions.
- Never invent music facts.
- Prefer official sources.

---

# Success Criteria

המערכת נחשבת מוכנה כאשר:

- שולחת הודעה יומית באופן אוטומטי.
- אינה מפרסמת כפילויות.
- אוספת מידע אמין.
- יוצרת תקציר איכותי.
- מוסיפה עובדות מעניינות.
- מציגה קישורים תקינים.
- פועלת ללא התערבות ידנית.