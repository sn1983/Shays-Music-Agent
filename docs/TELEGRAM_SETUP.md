# 📻 מדריך הפעלה — סוכן שיר היום בטלגרם

מדריך מלא מאפס: איך יוצרים את הבוט, איך מחברים אותו לטלגרם האישי שלכם,
ואיך גורמים לו לשלוח לכם הודעה אוטומטית כל יום ב-20:00.

**זמן משוער: 15 דקות.** אין צורך בידע בתכנות — רק להעתיק, להדביק ולהריץ.

---

## מה נבנה כאן

בכל יום, בשעה שתגדירו:

1. הסוכן בוחר שיר Pop/Rock אחד (90's / 2000's / 2010's / 2020's) שעוד לא פורסם.
2. חוקר אותו באינטרנט דרך Claude — אלבום, שנה, כותבים, מפיק, לינקים ועובדות.
3. כותב תקציר בעברית בסגנון שדרן רדיו.
4. שולח **לכל מי שנרשם לבוט** הודעה מעוצבת עם תמונת עטיפה וכפתורים
   ל-Spotify / YouTube / ויקיפדיה.
5. שומר את השיר במסד נתונים כדי שלעולם לא יחזור על עצמו.

כל אחד יכול להירשם בעצמו — הוא שולח `/start` לבוט, מקבל מיד הודעת ברוכים הבאים
עם שעת העדכון היומי, ומצטרף לתפוצה. `/stop` מסיר אותו.

---

## שלב 1 — יצירת הבוט אצל BotFather

1. פתחו טלגרם וחפשו את המשתמש **@BotFather** (עם הסימן הכחול ✅).
2. לחצו **Start** ושלחו לו את הפקודה:

   ```
   /newbot
   ```

3. הוא ישאל **"Alright, a new bot. How are we going to call it?"** — זה השם
   התצוגה של הבוט. אפשר בעברית. לדוגמה:

   ```
   שיר היום 🎵
   ```

4. אחר כך הוא יבקש **username** — חייב להיות באנגלית ולהסתיים ב-`bot`. לדוגמה:

   ```
   shay_music_daily_bot
   ```

   אם השם תפוס פשוט נסו וריאציה אחרת.

5. BotFather ישלח הודעה שמכילה שורה כזו:

   ```
   Use this token to access the HTTP API:
   8154392017:AAH9x7Kq2mVbN4pLdR6sTuWvXyZ1a2B3c4D
   ```

   **המחרוזת הארוכה הזו היא ה-TELEGRAM_BOT_TOKEN שלכם.** העתיקו אותה למקום בטוח.

> ⚠️ הטוקן הזה הוא סיסמה. מי שמחזיק בו יכול לשלוט בבוט. אל תשלחו אותו לאף אחד
> ואל תעלו אותו ל-GitHub. אם הוא נחשף — שלחו ל-BotFather `/revoke` וקבלו טוקן חדש.

### תוספות מומלצות (לא חובה)

עדיין אצל BotFather:

| פקודה | מה היא עושה |
|---|---|
| `/setdescription` | טקסט שמופיע לפני שלוחצים Start |
| `/setabouttext` | תיאור קצר בפרופיל הבוט |
| `/setuserpic` | תמונת פרופיל לבוט |

---

## שלב 2 — למצוא את ה-CHAT_ID שלכם

הבוט לא יכול לפנות אליכם ראשון — אתם חייבים לדבר איתו פעם אחת.

1. חפשו בטלגרם את ה-username שיצרתם (למשל `@shay_music_daily_bot`).
2. פתחו את השיחה ולחצו **Start** (או שלחו `/start`).
3. שלחו לו הודעה כלשהי, למשל `שלום`.
4. פתחו בדפדפן את הכתובת הבאה, כשאתם מחליפים את `<TOKEN>` בטוקן שלכם:

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

   דוגמה מלאה:
   `https://api.telegram.org/bot8154392017:AAH9x7Kq.../getUpdates`

5. תקבלו תשובה בפורמט JSON. חפשו בתוכה:

   ```json
   "chat": { "id": 512345678, "first_name": "Shay", "type": "private" }
   ```

   **המספר שליד `"id"` הוא ה-TELEGRAM_CHAT_ID שלכם** (במקרה הזה `512345678`).

> ⚠️ **הטעות הכי נפוצה:** לקחת את המספר שלפני הנקודתיים בטוקן (למשל `8154392017`
> מתוך `8154392017:AAH9x7Kq...`). **זה המזהה של הבוט, לא שלכם.** בוט לא יכול לשלוח
> הודעה לעצמו, ותקבלו `Forbidden: the bot can't send messages to the bot`.
> ודאו שבתוך ה-JSON בחרתם את ה-`id` שנמצא בתוך `"chat"` — זה שמופיע לצידו
> `"type": "private"` ו-`"is_bot": false`.

### אם `getUpdates` מחזיר רשימה ריקה

```json
{"ok":true,"result":[]}
```

זה אומר שטלגרם לא רשם הודעה נכנסת. פתרונות:

- ודאו ששלחתם הודעה לבוט **הנכון** (ה-username שיצרתם, לא ל-BotFather).
- שלחו לו עוד הודעה ורעננו את הדף.
- אם הרצתם בעבר סקריפט אחר עם אותו טוקן, ההודעות כבר "נצרכו" — פשוט שלחו הודעה חדשה.

### רוצים לשלוח לערוץ במקום לצ'אט אישי?

1. צרו ערוץ בטלגרם.
2. הוסיפו את הבוט כ-**Administrator** עם ההרשאה **Post Messages**.
3. ה-CHAT_ID של ערוץ ציבורי הוא פשוט `@channel_username`.
   בערוץ פרטי — פרסמו הודעה בערוץ, העבירו (Forward) אותה לבוט, ורוצו שוב `getUpdates`;
   ה-ID יופיע תחת `forward_from_chat` ויתחיל במינוס, למשל `-1001234567890`.

---

## שלב 3 — מפתח Claude API

1. היכנסו ל-<https://console.anthropic.com>
2. הירשמו / התחברו, וטענו קרדיט ב-**Billing** (עלות הרצה יומית היא סנטים בודדים).
3. **API Keys** → **Create Key** → העתיקו את המפתח שמתחיל ב-`sk-ant-...`.

> ⚠️ גם המפתח הזה הוא סוד. הוא מוצג פעם אחת בלבד — שמרו אותו מיד.

---

## שלב 4 — התקנה על המחשב

צריך **Python 3.11 ומעלה**. לבדיקה, בטרמינל:

```bash
python3 --version
```

ואז:

```bash
git clone https://github.com/sn1983/Shays-Music-Agent.git
cd Shays-Music-Agent

python3 -m venv .venv
source .venv/bin/activate        # ב-Windows:  .venv\Scripts\activate

pip install -r requirements.txt
```

---

## שלב 5 — קובץ ההגדרות `.env`

```bash
cp .env.example .env
```

פתחו את `.env` בעורך טקסט ומלאו את שלושת הערכים שאספתם:

```env
CLAUDE_API_KEY=sk-ant-המפתח-שלכם
TELEGRAM_BOT_TOKEN=8154392017:AAH9x7Kq2mVbN4pLdR6sTuWvXyZ1a2B3c4D
TELEGRAM_CHAT_ID=512345678

TIMEZONE=Asia/Jerusalem
POST_TIME=20:00
SONGS_PER_DAY=1
DRY_RUN=false
```

טבלת ההגדרות המלאה:

| משתנה | ברירת מחדל | מה זה עושה |
|---|---|---|
| `CLAUDE_API_KEY` | — | מפתח ה-API של Claude (חובה) |
| `CLAUDE_MODEL` | `claude-opus-5` | המודל שבו הסוכן משתמש |
| `CLAUDE_EFFORT` | `high` | עומק החשיבה: `low`/`medium`/`high`/`xhigh`/`max` |
| `TELEGRAM_BOT_TOKEN` | — | הטוקן מ-BotFather (חובה) |
| `TELEGRAM_CHAT_ID` | — | ה-ID שלכם: המנוי הראשון ויעד ההתראות (חובה) |
| `TELEGRAM_PARSE_MODE` | `HTML` | עיצוב ההודעה. `HTML` מומלץ, קיים גם `MarkdownV2` |
| `DATABASE_PATH` | `storage/music_agent.db` | קובץ ה-SQLite של היסטוריית השירים |
| `TIMEZONE` | `Asia/Jerusalem` | אזור הזמן לתזמון |
| `POST_TIME` | `20:00` | שעת השליחה היומית |
| `SONGS_PER_DAY` | `1` | כמה שירים בכל הרצה |
| `LOG_LEVEL` | `INFO` | רמת הלוגים |
| `DRY_RUN` | `false` | `true` = רק מדפיס למסך, לא שולח לטלגרם |

---

## שלב 6 — בדיקה שהכול עובד

### א. בדיקת החיבור לטלגרם

```bash
python main.py test-telegram
```

תוצאה תקינה — הודעה בטרמינל **וגם** הודעת בדיקה שמגיעה אליכם לטלגרם:

```
הבוט מחובר: @shay_music_daily_bot (שיר היום 🎵)
נשלחה הודעת בדיקה לצ'אט 512345678 (message_id=2)
```

### ב. הרצה יבשה — בלי לשלוח

```bash
python main.py run-once --dry-run
```

הסוכן יבחר שיר, יחקור אותו, ויציג את ההודעה המלאה במסך בלי לשלוח ובלי לשמור אותה
בהיסטוריה. לוקח בערך דקה-שתיים, כי הוא באמת מחפש באינטרנט.

### ג. השליחה האמיתית הראשונה

```bash
python main.py run-once
```

ההודעה תגיע לטלגרם, והשיר יירשם במסד הנתונים כדי שלא יחזור.

---

## שלב 7 — לגרום לזה לקרות כל יום אוטומטית

יש שלוש דרכים. בחרו אחת.

### אפשרות א' — הכי פשוטה: להשאיר את התוכנית רצה

```bash
python main.py schedule
```

התוכנית נשארת פתוחה ושולחת כל יום ב-`POST_TIME` לפי `TIMEZONE`.
**החיסרון:** אם המחשב נכבה או נכנס לשינה, לא תישלח הודעה.

לעצירה: `Ctrl+C`.

### אפשרות ב' — GitHub Actions (מומלץ: רץ בענן, המחשב יכול להיות כבוי)

הפרויקט כולל כבר workflow מוכן בקובץ `.github/workflows/daily-song.yml`.

1. העלו את הפרויקט ל-GitHub (בלי הקובץ `.env` — הוא כבר ב-`.gitignore`).
2. ב-GitHub: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**,
   והוסיפו שלושה סודות:

   | Name | Secret |
   |---|---|
   | `CLAUDE_API_KEY` | המפתח שלכם |
   | `TELEGRAM_BOT_TOKEN` | הטוקן שלכם |
   | `TELEGRAM_CHAT_ID` | ה-ID שלכם |

3. **Settings** → **Actions** → **General** → תחת *Workflow permissions* בחרו
   **Read and write permissions** (זה מאפשר לשמור את היסטוריית השירים בחזרה לריפו).
4. זהו. הריצה מתבצעת אוטומטית כל יום.
   לבדיקה מיידית: לשונית **Actions** → *Daily Song* → **Run workflow**.

> 🕐 **למה ארבע שעות ב-cron?** שתי סיבות. הראשונה: GitHub מריץ לפי UTC וישראל מזיזה
> שעון פעמיים בשנה. השנייה, והחשובה יותר: **GitHub לא מבטיח דיוק בתזמון** — הרצה
> שנקבעה לשעה עגולה מתחילה בפועל 20 עד 70 דקות מאוחר יותר, כי זו המשבצת העמוסה ביותר.
> לכן ה-workflow מבקש ארבע משבצות (בדקה :07, לא בשעה עגולה), והקוד מפרסם **בראשונה
> שנוחתת ב-20:00 או אחריה**. `--once-per-day` דואג שהשאר לא ישלחו שוב.
> התוצאה: הודעה אחת ביום, גם כשהתזמון מתעכב וגם אחרי מעבר שעון.

### אפשרות ג' — cron על שרת או Raspberry Pi

```bash
crontab -e
```

והוסיפו שורה (עדכנו את הנתיב):

```cron
0 20 * * * cd /home/shay/Shays-Music-Agent && .venv/bin/python main.py run-once --once-per-day >> logs/cron.log 2>&1
```

---

## איך אנשים נוספים נרשמים

שלחו להם את הקישור לבוט: `https://t.me/<username-של-הבוט>` (למשל
`https://t.me/shay_music_daily_bot`).

מה שקורה אצלם:

1. הם לוחצים **Start** או שולחים `/start`.
2. מגיעה אליהם **הודעת ברוכים הבאים** עם הסבר קצר ו**שעת העדכון היומי**.
3. מאותו רגע הם מקבלים את השיר כל יום, יחד עם כולם.
4. `/stop` מסיר אותם, `/start` מחזיר.

### כמה זמן לוקח עד שהם מקבלים את הודעת הברוכים הבאים?

| איך מריצים | תגובה |
|---|---|
| GitHub Actions | עד כ-15 דקות — `sync-subscribers` רץ כל רבע שעה |
| `python main.py bot` על מחשב שדולק תמיד | מיידי |

אם אתם רוצים תגובה מיידית בלי להשאיר מחשב דולק, אפשר להוריד את ה-cron של
`*/15` בקובץ ה-workflow ל-`*/5` (זה המינימום ש-GitHub מאפשר).

### לראות מי רשום

**מהטלפון או מהדפדפן** — הקובץ `storage/subscribers.md` בריפו:
<https://github.com/sn1983/Shays-Music-Agent/blob/main/storage/subscribers.md>
הוא מתעדכן אוטומטית בכל הרצה (כל 15 דקות) ומציג את השמות, תאריכי ההצטרפות
ומי הסיר את עצמו.

**מהמחשב**, עם המזהים המלאים:

```bash
python main.py subscribers          # רק הפעילים
python main.py subscribers --all    # כולל מי שהסיר את עצמו
```

> 🔒 המזהים בקובץ ה-Markdown מוצגים חלקית (`738***373`) בכוונה — הקובץ נמצא
> בריפו, ומזהה מלא יחד עם שם פרטי מזהה אדם אמיתי.

---

## פקודות שימושיות

| פקודה | מה היא עושה |
|---|---|
| `python main.py test-telegram` | בודקת את הטוקן ואת ה-chat id |
| `python main.py sync-subscribers` | קולטת נרשמים חדשים ושולחת להם ברוכים הבאים |
| `python main.py bot` | מאזין רציף — נרשמים מקבלים תשובה מיידית |
| `python main.py subscribers` | מציגה את רשימת המנויים |
| `python main.py run-once` | בוחר, חוקר ושולח שיר עכשיו |
| `python main.py run-once --dry-run` | אותו דבר, רק מדפיס במסך |
| `python main.py run-once --once-per-day` | לא שולח אם כבר פורסם שיר היום |
| `python main.py schedule` | נשאר פעיל ושולח כל יום ב-`POST_TIME` |
| `python main.py history --limit 30` | מציג את השירים האחרונים שפורסמו |
| `python main.py stats` | פילוח לפי עשורים מול היעד |
| `python main.py init-db` | יוצר את מסד הנתונים |

---

## פתרון תקלות

| מה קורה | למה | מה עושים |
|---|---|---|
| `Unauthorized (error_code=401)` | הטוקן שגוי או בוטל | העתיקו מחדש מ-BotFather; ודאו שאין רווחים או גרשיים ב-`.env` |
| `chat not found (error_code=400)` | ה-chat id שגוי, או שלא לחצתם Start | שלחו `/start` לבוט וחזרו על שלב 2 |
| `the bot can't send messages to the bot (403)` | ב-`TELEGRAM_CHAT_ID` הוזן המזהה של הבוט | קחו את ה-`id` מתוך `"chat"` ב-getUpdates, לא את המספר שלפני הנקודתיים בטוקן |
| `bot was blocked by the user` | חסמתם את הבוט | פתחו את השיחה בטלגרם ולחצו **Unblock** |
| `getUpdates` מחזיר `result: []` | טלגרם לא רשם הודעה נכנסת | שלחו הודעה נוספת לבוט ורעננו |
| `שגיאת הגדרות: Missing required environment variable` | חסר ערך ב-`.env` | ודאו שהקובץ נקרא בדיוק `.env` ויושב בתיקיית הפרויקט |
| `authentication_error` מ-Claude | מפתח לא תקין | צרו מפתח חדש בקונסולה של Anthropic |
| `credit balance is too low` | אין קרדיט | טענו יתרה ב-Billing |
| ההודעה מגיעה בלי תמונה | לא נמצאה עטיפה מאומתת | תקין ומכוון: הסוכן לא ממציא לינקים, ושולח טקסט בלבד |
| `No acceptable song after 4 attempts` | כללי החזרתיות חסמו כל בחירה | לרוב זמני. `python main.py history` יראה מה כבר פורסם |
| `529 Overloaded` / `The Claude API stayed unavailable` | ה-API של Claude היה עמוס | הסוכן מנסה שוב אוטומטית (20/60/120 שניות) ואז עובר למודל הגיבוי. אם גם זה נכשל — הריצו שוב מאוחר יותר |
| `חסרות הגדרות` בהרצת GitHub Actions | סוד חסר ב-Actions | Settings → Secrets and variables → Actions |
| ההודעה נראית עם `\` או תווים מוזרים | מצב עיצוב לא מתאים | הגדירו `TELEGRAM_PARSE_MODE=HTML` |

לוגים מלאים נשמרים ב-`logs/agent.log`.

---

## שאלות נפוצות

**כמה זה עולה?**
הרצה יומית אחת עולה בדרך כלל כמה סנטים ב-Claude API. טלגרם חינם לחלוטין.

**איך משנים את שעת השליחה?**
`POST_TIME=21:30` בקובץ `.env` (במצב `schedule` או cron). ב-GitHub Actions צריך לעדכן
גם את שעות ה-cron בקובץ ה-workflow וגם את `--local-hour`.

**איך שולחים שני שירים ביום?**
`SONGS_PER_DAY=2`.

**האם שיר יכול לחזור פעמיים?**
לא. כל שיר נשמר ב-`storage/music_agent.db` ונחסם לצמיתות. בנוסף, אמן לא חוזר במשך
30 פרסומים ושנת יציאה לא חוזרת במשך 10 פרסומים.

**איך מוסיפים ז'אנר שהסוכן חוסם?**
`BLOCKED_GENRES` בקובץ `src/music_agent/music/selector.py`.

**איך משנים את חלוקת העשורים?**
`DECADE_WEIGHTS` באותו קובץ. ברירת המחדל: 30% / 30% / 20% / 20%.

**אני רוצה למחוק שיר מההיסטוריה כדי שיוכל לחזור:**

```bash
sqlite3 storage/music_agent.db "DELETE FROM published_songs WHERE title = 'Torn';"
```
