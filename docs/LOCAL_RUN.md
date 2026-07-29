# 💻 הרצה מקומית על המחשב שלכם (בלי Git)

מדריך להורדת הפרויקט והרצתו על Windows או Mac, בלי להתקין Git ובלי להכיר אותו.

---

## שלב 1 — להוריד את הפרויקט

### דרך א' — ישירות מ-GitHub (מומלץ, תמיד הגרסה העדכנית)

1. היכנסו ל-<https://github.com/sn1983/Shays-Music-Agent>
2. לחצו על הכפתור הירוק **Code**
3. בחרו **Download ZIP**

או בקישור ישיר:
<https://github.com/sn1983/Shays-Music-Agent/archive/refs/heads/main.zip>

### דרך ב' — קובץ ה-ZIP שנשלח בצ'אט

אותו תוכן בדיוק, כולל קובץ `.env` ריק שמוכן למילוי.

### לחלץ

- **Windows:** קליק ימני על ה-ZIP → **Extract All** → בחרו מיקום, למשל `C:\Projects`
- **Mac:** דאבל-קליק על ה-ZIP

תקבלו תיקייה בשם `Shays-Music-Agent` (או `Shays-Music-Agent-main` אם הורדתם מ-GitHub).

> ⚠️ **אל תשאירו את התיקייה בתוך Downloads**, ועדיף בלי עברית או רווחים בנתיב.
> `C:\Projects\Shays-Music-Agent` — מצוין. `C:\Users\שי\שולחן העבודה\מוזיקה` — עלול לעשות בעיות.

---

## שלב 2 — להתקין Python

צריך **Python 3.11 ומעלה**.

**Windows:**
1. <https://www.python.org/downloads/>
2. בהתקנה, **סמנו את התיבה "Add python.exe to PATH"** בתחתית החלון הראשון. זה קריטי —
   בלי זה הפקודות בהמשך לא יעבדו.

**Mac:** מותקן בדרך כלל. אם לא: <https://www.python.org/downloads/macos/>

**לבדוק שזה עבד** — פתחו טרמינל והריצו:

```bash
python --version
```

אם זה לא עובד, נסו `python3 --version`. אם גם זה לא — ההתקנה לא הוסיפה ל-PATH,
התקינו מחדש עם התיבה מסומנת.

---

## שלב 3 — לפתוח טרמינל בתיקיית הפרויקט

**Windows:** פתחו את התיקייה ב-File Explorer, לחצו על שורת הכתובת למעלה,
הקלידו `powershell` ו-Enter.

**Mac:** קליק ימני על התיקייה → **Services** → **New Terminal at Folder**.

לוודא שאתם במקום הנכון — הריצו `dir` (ב-Windows) או `ls` (ב-Mac). אתם אמורים
לראות את `main.py` ואת `requirements.txt`.

---

## שלב 4 — סביבה וירטואלית והתקנת ספריות

זה מתקין את הספריות בתוך תיקיית הפרויקט בלבד, בלי ללכלך את המחשב.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

אם תקבלו שגיאה אדומה על **execution policy**, הריצו פעם אחת ואז נסו שוב:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**Mac:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

כשזה עובד, יופיע `(.venv)` בתחילת שורת הטרמינל. **בכל פעם שתפתחו טרמינל חדש
צריך להריץ שוב את שורת ה-activate** (רק אותה, לא את שתי האחרות).

---

## שלב 5 — לערוך את קובץ ה-`.env` ⭐

זה הקובץ שמחזיק את המפתחות שלכם. הוא **לא** נשמר ב-GitHub — הוא נשאר רק אצלכם.

אם יש לכם רק `.env.example`, צרו ממנו עותק:

```powershell
# Windows
copy .env.example .env
```

```bash
# Mac
cp .env.example .env
```

ואז פתחו אותו לעריכה:

```powershell
# Windows — נפתח ב-Notepad
notepad .env
```

```bash
# Mac — נפתח ב-TextEdit
open -e .env
```

מלאו את שלושת השדות החיוניים:

```env
CLAUDE_API_KEY=sk-ant-המפתח-שלכם
TELEGRAM_BOT_TOKEN=8154392017:AAH9x7Kq...
TELEGRAM_CHAT_ID=512345678
```

מאיפה משיגים אותם: **[docs/TELEGRAM_SETUP.md](TELEGRAM_SETUP.md)** שלבים 1–3.

### שלוש טעויות נפוצות בקובץ הזה

1. **גרשיים.** כתבו `TELEGRAM_CHAT_ID=512345678` ולא `TELEGRAM_CHAT_ID="512345678"`.
2. **רווחים סביב ה-`=`.** בלי. `KEY=value`, לא `KEY = value`.
3. **Windows שומר בשם `.env.txt`.** ב-Notepad בחרו **File → Save As**, ובשדה
   *Save as type* בחרו **All Files**, ואז שמרו בשם `.env` בדיוק. כדי לוודא —
   הפעילו ב-File Explorer את **View → File name extensions** ובדקו שהקובץ הוא
   `.env` ולא `.env.txt`.

---

## שלב 6 — להריץ

```bash
python main.py test-telegram
```

אמורה להגיע אליכם הודעת בדיקה בטלגרם. אם כן — הכול מחובר.

**הרצה יבשה** (בוחר שיר, חוקר, מדפיס במסך, לא שולח ולא שומר):

```bash
python main.py run-once --dry-run
```

לוקח דקה-שתיים, כי הסוכן באמת מחפש באינטרנט.

**שליחה אמיתית:**

```bash
python main.py run-once
```

**כל הפקודות:**

| פקודה | מה היא עושה |
|---|---|
| `python main.py test-telegram` | בדיקת חיבור לטלגרם |
| `python main.py test-facebook` | בדיקת חיבור לפייסבוק |
| `python main.py run-once --dry-run` | הרצה יבשה |
| `python main.py run-once` | שליחה אמיתית |
| `python main.py schedule` | נשאר פעיל ושולח כל יום ב-20:00 |
| `python main.py history` | מה כבר פורסם |
| `python main.py stats` | פילוח לפי עשורים |
| `python -m pytest` | הרצת הבדיקות (42 בדיקות, לא נוגעות ב-API) |

---

## תקלות ספציפיות להרצה מקומית

| מה קורה | הפתרון |
|---|---|
| `python: command not found` | נסו `python3` במקום `python`. ב-Windows — התקינו מחדש עם "Add to PATH" |
| `'.venv\Scripts\Activate.ps1' cannot be loaded` | הריצו `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `ModuleNotFoundError: No module named 'anthropic'` | שכחתם `activate`, או שלא הרצתם `pip install -r requirements.txt` |
| `שגיאת הגדרות: Missing required environment variable` | הקובץ נשמר כ-`.env.txt`, או שהוא לא באותה תיקייה עם `main.py` |
| העברית בטרמינל נראית כג'יבריש (Windows) | הריצו `chcp 65001` לפני הפקודה. ב-Windows Terminal החדש זה לא קורה |
| הקובץ `.env` נשמר עם קידוד שגוי | שמרו כ-**UTF-8**. ב-Notepad זה בתפריט Save As למטה |
| רוצים למחוק הכול ולהתחיל מחדש | פשוט מחקו את התיקייה. שום דבר לא הותקן מחוץ אליה |

---

## איפה הכול נשמר אצלכם

| מיקום | מה יש שם |
|---|---|
| `.env` | המפתחות שלכם — **רק על המחשב שלכם** |
| `storage/music_agent.db` | היסטוריית השירים שפורסמו. מוחקים אותו = הסוכן שוכח הכול |
| `logs/agent.log` | לוג מלא של כל הרצה, שימושי כשמשהו נכשל |
| `.venv/` | הספריות המותקנות. אפשר למחוק ולבנות מחדש בכל רגע |

---

## עדכון לגרסה חדשה בלי Git

הורידו ZIP חדש, חלצו לתיקייה חדשה, והעתיקו אליה שני דברים מהישנה:

1. את הקובץ `.env`
2. את התיקייה `storage/` (כדי לא לאבד את היסטוריית השירים)

ואז `pip install -r requirements.txt` בתיקייה החדשה.
