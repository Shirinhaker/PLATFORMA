"""
Platforma — ma'lumotlar bazasi (SQLite).

Jadval tuzilishi kelishilgan dizaynga mos:
  users         - barcha foydalanuvchilar (oddiy + biznes egalari), login/parol, Telegram bog'lanishi
  businesses    - biznes profillari (nomi, yo'nalishi, joyi, aloqa)
  specialists   - mutaxasislik ma'lumotlari (davlat ishchisi rejimi bilan)
  items         - biznes mahsulot/xizmatlari
  listings      - e'lonlar (ko'rinish turi: butun platforma / faqat sahifa mehmonlari)
  listing_media - e'lon rasm/videolari (Telegram file_id sifatida — serverga yuk tushmaydi)
  follows       - obunalar (odamga ham, biznesga ham)
  saved         - saqlanganlar
  orders        - buyurtma va navbat yozuvlari (user/business aktyorlar bo'yicha)
  debtors/qarz_tx - qarz daftari (biznes kabineti bo'limi)
  pending_regs  - ro'yxatdan o'tish kutilmoqda (kod tasdiqlangunicha)
  auth_codes    - kirishdagi tasdiqlash kodlari
"""

import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "platforma.db")


def db():
    # Baza papkasi mavjudligini ta'minlaymiz (Railway volume uchun)
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id         INTEGER UNIQUE,
            username      TEXT DEFAULT '',                  -- Telegram username (@siz)
            login         TEXT UNIQUE NOT NULL,
            pass_hash     TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user',     -- 'user' | 'business'
            name          TEXT NOT NULL,
            phone         TEXT DEFAULT '',
            region        TEXT DEFAULT '',                  -- viloyat/shahar
            district      TEXT DEFAULT '',                  -- tuman
            mahalla       TEXT DEFAULT '',
            lat           REAL,                             -- foydalanuvchining bosh sahifa manzil koordinatasi
            lng           REAL,                             -- foydalanuvchining bosh sahifa manzil koordinatasi
            avatar_file   TEXT DEFAULT '',                  -- Telegram file_id
            created_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS businesses(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL UNIQUE,
            name          TEXT NOT NULL,
            yon           TEXT DEFAULT '',                  -- faoliyat yo'nalishi (20 tadan biri)
            tur           TEXT DEFAULT '',                  -- faoliyat turi
            descr         TEXT DEFAULT '',
            phone         TEXT DEFAULT '',
            telegram      TEXT DEFAULT '',
            work_hours    TEXT DEFAULT '',
            address       TEXT DEFAULT '',
            lat           REAL,
            lng           REAL,
            logo_file     TEXT DEFAULT '',
            biz_login     TEXT,                             -- biznes uchun alohida login
            biz_pass_hash TEXT,                             -- biznes uchun alohida parol
            status        TEXT DEFAULT 'active',
            map_visible   INTEGER DEFAULT 0,                -- bosh xaritada platforma ko'rsatadigan biznesmi
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS specialists(
            user_id       INTEGER PRIMARY KEY,
            kasb          TEXT DEFAULT '',
            descr         TEXT DEFAULT '',
            narx          TEXT DEFAULT '',
            hudud         TEXT DEFAULT '',
            is_gov        INTEGER DEFAULT 0,                -- davlat ishchisimi
            org           TEXT DEFAULT '',                  -- tashkilot
            dept          TEXT DEFAULT '',                  -- bo'lim
            lavozim       TEXT DEFAULT '',
            work_hours    TEXT DEFAULT '',                  -- ish vaqtidagi qabul (davlat ishchisi)
            after_hours   TEXT DEFAULT '',                  -- ishdan tashqari qabul
            visible       INTEGER DEFAULT 0,                -- ko'rinaman/ko'rinmayman
            available     INTEGER DEFAULT 1,                -- bo'shman/bandman
            lat           REAL,
            lng           REAL,
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS items(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id   INTEGER NOT NULL,
            name          TEXT NOT NULL,
            price         TEXT DEFAULT '',
            note          TEXT DEFAULT '',
            kind          TEXT DEFAULT 'product',           -- 'product' | 'service'
            photo_file    TEXT DEFAULT '',
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS listings(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,                 -- kim joylagan
            business_id   INTEGER,                          -- biznes nomidan bo'lsa
            cat           TEXT NOT NULL,                    -- toifa (uy, moshina, ish...)
            title         TEXT NOT NULL,
            price         TEXT DEFAULT '',
            descr         TEXT DEFAULT '',
            address       TEXT DEFAULT '',
            lat           REAL,
            lng           REAL,
            visibility    TEXT DEFAULT 'all',               -- 'all' | 'own' (faqat sahifa mehmonlari)
            status        TEXT DEFAULT 'active',
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS listing_media(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id    INTEGER NOT NULL,
            tg_file_id    TEXT NOT NULL,                    -- Telegramda saqlanadi (bepul)
            mtype         TEXT DEFAULT 'photo',             -- 'photo' | 'video'
            pos           INTEGER DEFAULT 0,
            FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS follows(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id   INTEGER NOT NULL,                 -- kim obuna bo'ldi (user id)
            target_kind   TEXT NOT NULL,                    -- 'user' | 'business'
            target_id     INTEGER NOT NULL,
            created_at    INTEGER NOT NULL,
            UNIQUE(follower_id, target_kind, target_id),
            FOREIGN KEY(follower_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS saved(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            target_kind   TEXT NOT NULL,                    -- 'listing' | 'business'
            target_id     INTEGER NOT NULL,
            created_at    INTEGER NOT NULL,
            UNIQUE(user_id, target_kind, target_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS orders(
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_kind      TEXT NOT NULL DEFAULT 'user',      -- 'user' | 'business'
            customer_actor_id  INTEGER NOT NULL,                 -- user.id yoki businesses.id
            customer_user_id   INTEGER NOT NULL,                 -- Telegram egasi user.id
            provider_kind      TEXT NOT NULL DEFAULT 'business',  -- 'user' | 'business'
            provider_actor_id  INTEGER NOT NULL,                 -- user.id yoki businesses.id
            provider_user_id   INTEGER NOT NULL,                 -- Telegram egasi user.id
            item_id            INTEGER,
            listing_id         INTEGER,
            title              TEXT DEFAULT '',                  -- buyurtma nomi
            note               TEXT DEFAULT '',                  -- mijoz izohi
            phone              TEXT DEFAULT '',
            order_type         TEXT DEFAULT 'delivery',          -- delivery/pickup/booking
            address            TEXT DEFAULT '',                  -- yetkazib berish manzili yoki joy
            desired_time       TEXT DEFAULT '',                  -- mijoz xohlagan vaqt
            qty                INTEGER DEFAULT 1,
            status             TEXT DEFAULT 'new',               -- new/accepted/rejected/done/cancelled
            created_at         INTEGER NOT NULL,
            updated_at         INTEGER NOT NULL,
            FOREIGN KEY(customer_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(provider_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS order_items(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL,
            item_id     INTEGER,
            item_name   TEXT NOT NULL,
            price_text  TEXT DEFAULT '',
            qty         INTEGER DEFAULT 1,
            line_total  INTEGER DEFAULT 0,
            note        TEXT DEFAULT '',
            created_at  INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS debtors(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id   INTEGER NOT NULL,
            name          TEXT NOT NULL,
            phone         TEXT DEFAULT '',
            note          TEXT DEFAULT '',
            due           TEXT DEFAULT '',
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS qarz_tx(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            debtor_id     INTEGER NOT NULL,
            type          TEXT NOT NULL,                    -- 'debt' | 'payment'
            amount        INTEGER NOT NULL,
            date          TEXT NOT NULL,
            note          TEXT DEFAULT '',
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(debtor_id) REFERENCES debtors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pending_regs(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id         INTEGER NOT NULL,
            role          TEXT NOT NULL,
            login         TEXT NOT NULL,
            pass_hash     TEXT NOT NULL,
            payload       TEXT NOT NULL,                    -- forma ma'lumotlari (JSON)
            code          TEXT NOT NULL,
            expires_at    INTEGER NOT NULL,
            created_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS login_requests(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,                 -- kimning akkauntiga kirilmoqchi
            device_tg     INTEGER NOT NULL,                 -- kirayotgan qurilma Telegram ID
            device_name   TEXT DEFAULT '',                  -- kirayotgan qurilma nomi (ko'rsatish uchun)
            status        TEXT DEFAULT 'pending',           -- 'pending' | 'approved' | 'rejected'
            expires_at    INTEGER NOT NULL,
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS media_inbox(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id         INTEGER NOT NULL,                 -- kim yuborgan
            file_id       TEXT NOT NULL,                    -- Telegram file_id
            mtype         TEXT DEFAULT 'photo',
            created_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages(
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id         INTEGER NOT NULL,                 -- yuboruvchining egasi user id (moslik uchun)
            receiver_id       INTEGER NOT NULL,                 -- qabul qiluvchining egasi user id (moslik uchun)
            sender_kind       TEXT DEFAULT 'user',              -- 'user' | 'business'
            sender_actor_id   INTEGER,                          -- user.id yoki businesses.id
            receiver_kind     TEXT DEFAULT 'user',              -- 'user' | 'business'
            receiver_actor_id INTEGER,                          -- user.id yoki businesses.id
            text              TEXT DEFAULT '',
            is_read           INTEGER DEFAULT 0,
            created_at        INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notify_filters(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            cat           TEXT NOT NULL,
            region        TEXT DEFAULT '',
            district      TEXT DEFAULT '',
            price_min     INTEGER DEFAULT 0,
            price_max     INTEGER DEFAULT 0,
            keyword       TEXT DEFAULT '',
            created_at    INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_inbox_tg       ON media_inbox(tg_id);
        CREATE INDEX IF NOT EXISTS idx_users_tg       ON users(tg_id);
        CREATE INDEX IF NOT EXISTS idx_biz_user       ON businesses(user_id);
        CREATE INDEX IF NOT EXISTS idx_items_biz      ON items(business_id);
        CREATE INDEX IF NOT EXISTS idx_list_user      ON listings(user_id);
        CREATE INDEX IF NOT EXISTS idx_list_cat       ON listings(cat, status);
        CREATE INDEX IF NOT EXISTS idx_media_list     ON listing_media(listing_id);
        CREATE INDEX IF NOT EXISTS idx_follows_t      ON follows(target_kind, target_id);
        CREATE INDEX IF NOT EXISTS idx_saved_u        ON saved(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_kind, customer_actor_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_provider ON orders(provider_kind, provider_actor_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_debtors_biz    ON debtors(business_id);
        CREATE INDEX IF NOT EXISTS idx_qtx_debtor     ON qarz_tx(debtor_id);
        """
    )
    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    """Eski bazaga yetishmayotgan ustun va jadvallarni xavfsiz qo'shadi (ma'lumot yo'qolmaydi)."""
    # users.username ustuni bormi?
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "username" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN username TEXT DEFAULT ''")
    if "lat" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN lat REAL")
    if "lng" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN lng REAL")
    # login_requests jadvali bormi? (CREATE TABLE IF NOT EXISTS yuqorida bor, lekin ishonch uchun)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS login_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_tg INTEGER NOT NULL,
            device_name TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )"""
    )
    # Chat xabarlari jadvali — user va biznes aktyorlari ajratilgan holda
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id         INTEGER NOT NULL,      -- yuboruvchi egasi user id (moslik uchun)
            receiver_id       INTEGER NOT NULL,      -- qabul qiluvchi egasi user id (moslik uchun)
            sender_kind       TEXT DEFAULT 'user',   -- 'user' | 'business'
            sender_actor_id   INTEGER,               -- user.id yoki businesses.id
            receiver_kind     TEXT DEFAULT 'user',   -- 'user' | 'business'
            receiver_actor_id INTEGER,               -- user.id yoki businesses.id
            text              TEXT DEFAULT '',
            is_read           INTEGER DEFAULT 0,     -- qabul qiluvchi aktyor o'qiganmi
            created_at        INTEGER NOT NULL
        )"""
    )
    mcols = [r["name"] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "sender_kind" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN sender_kind TEXT DEFAULT 'user'")
    if "sender_actor_id" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN sender_actor_id INTEGER")
    if "receiver_kind" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN receiver_kind TEXT DEFAULT 'user'")
    if "receiver_actor_id" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN receiver_actor_id INTEGER")
    # Eski xabarlar user -> user deb belgilab qo'yiladi, ma'lumot yo'qolmaydi.
    conn.execute("UPDATE messages SET sender_kind='user' WHERE sender_kind IS NULL OR sender_kind=''")
    conn.execute("UPDATE messages SET receiver_kind='user' WHERE receiver_kind IS NULL OR receiver_kind=''")
    conn.execute("UPDATE messages SET sender_actor_id=sender_id WHERE sender_actor_id IS NULL")
    conn.execute("UPDATE messages SET receiver_actor_id=receiver_id WHERE receiver_actor_id IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_pair ON messages(sender_id, receiver_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_actor_pair ON messages(sender_kind, sender_actor_id, receiver_kind, receiver_actor_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_receiver_actor ON messages(receiver_kind, receiver_actor_id, is_read)")
    # Buyurtmalar / navbatlar — user va biznes aktyorlari ajratilgan holda
    conn.execute(
        """CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_kind      TEXT NOT NULL DEFAULT 'user',
            customer_actor_id  INTEGER NOT NULL,
            customer_user_id   INTEGER NOT NULL,
            provider_kind      TEXT NOT NULL DEFAULT 'business',
            provider_actor_id  INTEGER NOT NULL,
            provider_user_id   INTEGER NOT NULL,
            item_id            INTEGER,
            listing_id         INTEGER,
            title              TEXT DEFAULT '',
            note               TEXT DEFAULT '',
            phone              TEXT DEFAULT '',
            order_type         TEXT DEFAULT 'delivery',
            address            TEXT DEFAULT '',
            desired_time       TEXT DEFAULT '',
            qty                INTEGER DEFAULT 1,
            status             TEXT DEFAULT 'new',
            created_at         INTEGER NOT NULL,
            updated_at         INTEGER NOT NULL
        )"""
    )
    ocols = [r["name"] for r in conn.execute("PRAGMA table_info(orders)").fetchall()]
    if "order_type" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN order_type TEXT DEFAULT 'delivery'")
    if "address" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN address TEXT DEFAULT ''")
    if "desired_time" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN desired_time TEXT DEFAULT ''")
    conn.execute("UPDATE orders SET order_type='delivery' WHERE order_type IS NULL OR order_type=''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_kind, customer_actor_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_provider ON orders(provider_kind, provider_actor_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, created_at)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS order_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL,
            item_id     INTEGER,
            item_name   TEXT NOT NULL,
            price_text  TEXT DEFAULT '',
            qty         INTEGER DEFAULT 1,
            line_total  INTEGER DEFAULT 0,
            note        TEXT DEFAULT '',
            created_at  INTEGER NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_order_items_item ON order_items(item_id)")
    # Bildirishnoma filtrlari — foydalanuvchi qiziqishlari (tur+hudud+narx+kalit so'z)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS notify_filters(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            cat       TEXT NOT NULL,            -- e'lon turi (uy/ish/moshina/hayvon/texnika/boshqa)
            region    TEXT DEFAULT '',          -- viloyat ('' = istalgan)
            district  TEXT DEFAULT '',          -- tuman ('' = istalgan)
            price_min INTEGER DEFAULT 0,        -- 0 = chegara yo'q
            price_max INTEGER DEFAULT 0,        -- 0 = chegara yo'q
            keyword   TEXT DEFAULT '',          -- kalit so'z ('' = istalgan)
            created_at INTEGER NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nf_cat ON notify_filters(cat)")
    # businesses uchun alohida login/parol ustunlari
    bcols = [r["name"] for r in conn.execute("PRAGMA table_info(businesses)").fetchall()]
    if "biz_login" not in bcols:
        conn.execute("ALTER TABLE businesses ADD COLUMN biz_login TEXT")
    if "biz_pass_hash" not in bcols:
        conn.execute("ALTER TABLE businesses ADD COLUMN biz_pass_hash TEXT")
    if "map_visible" not in bcols:
        conn.execute("ALTER TABLE businesses ADD COLUMN map_visible INTEGER DEFAULT 0")
