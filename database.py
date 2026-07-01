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

        CREATE TABLE IF NOT EXISTS item_groups(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id   INTEGER NOT NULL,
            name          TEXT NOT NULL,                    -- guruh nomi
            kind          TEXT DEFAULT 'product',           -- 'product' | 'service'
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS items(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id   INTEGER NOT NULL,
            group_id      INTEGER,                          -- NULL bo'lsa: Guruhsiz
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
            delivery_lat       REAL,                             -- yetkazib berish metkasi latitude
            delivery_lng       REAL,                             -- yetkazib berish metkasi longitude
            qty                INTEGER DEFAULT 1,
            status             TEXT DEFAULT 'new',               -- new/accepted/rejected/done/cancelled
            created_at         INTEGER NOT NULL,
            updated_at         INTEGER NOT NULL,
            provider_seen_at   INTEGER DEFAULT 0,                  -- biznes egasi ko'rgan vaqt
            customer_seen_at   INTEGER DEFAULT 0,                  -- mijoz status yangilanishini ko'rgan vaqt
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

        CREATE TABLE IF NOT EXISTS order_messages(
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        INTEGER NOT NULL,                  -- qaysi buyurtmaga tegishli
            sender_kind     TEXT NOT NULL DEFAULT 'user',      -- 'user' | 'business'
            sender_actor_id INTEGER NOT NULL,                  -- user.id yoki businesses.id
            sender_user_id  INTEGER NOT NULL,                  -- Telegram egasi user.id
            text            TEXT DEFAULT '',
            media_type      TEXT DEFAULT 'text',             -- 'text' | 'photo'
            media_url       TEXT DEFAULT '',                 -- serverdagi rasm manzili
            file_name       TEXT DEFAULT '',                 -- asl fayl nomi
            reply_to_id     INTEGER,                         -- qaysi xabarga javob berilgan
            edited_at       INTEGER DEFAULT 0,                -- tahrirlangan vaqt
            deleted_at      INTEGER DEFAULT 0,                -- o'chirilgan vaqt
            is_deleted      INTEGER DEFAULT 0,                -- 1 bo'lsa xabar o'chirilgan
            created_at      INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(sender_user_id) REFERENCES users(id) ON DELETE CASCADE
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
            media_type        TEXT DEFAULT 'text',               -- 'text' | 'photo'
            media_url         TEXT DEFAULT '',                   -- rasm server manzili
            file_name         TEXT DEFAULT '',                   -- serverdagi fayl nomi
            reply_to_id       INTEGER,                           -- qaysi xabarga javob
            edited_at         INTEGER DEFAULT 0,                 -- tahrirlangan vaqt
            deleted_at        INTEGER DEFAULT 0,                 -- o'chirilgan vaqt
            is_deleted        INTEGER DEFAULT 0,                 -- xavfsiz o'chirish belgisi
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

        CREATE TABLE IF NOT EXISTS drivers(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL UNIQUE,           -- haydovchi (foydalanuvchi)
            phone         TEXT DEFAULT '',
            car_model     TEXT DEFAULT '',                   -- mashina rusumi
            car_color     TEXT DEFAULT '',                   -- rangi
            car_plate     TEXT DEFAULT '',                   -- davlat raqami
            service       TEXT DEFAULT 'taxi',               -- 'taxi' | 'dostavka' | 'both'
            available     INTEGER DEFAULT 1,                 -- 1 = bo'shman, 0 = bandman
            rating_sum    INTEGER DEFAULT 0,                 -- reyting yig'indisi (keyin)
            rating_cnt    INTEGER DEFAULT 0,                 -- baholar soni (keyin)
            balance       INTEGER DEFAULT 0,                 -- hisob (keyin, to'lov uchun)
            status        TEXT DEFAULT 'active',
            created_at    INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS rides(
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,                -- mijoz (foydalanuvchi)
            kind            TEXT NOT NULL DEFAULT 'taxi',    -- 'taxi' | 'dostavka'
            from_addr       TEXT DEFAULT '',
            to_addr         TEXT DEFAULT '',
            from_lat        REAL,                            -- xaritadan: boshlanish koordinatasi
            from_lng        REAL,
            to_lat          REAL,                            -- xaritadan: manzil koordinatasi
            to_lng          REAL,
            dist_km         REAL,                            -- masofa (km)
            dur_min         INTEGER,                         -- taxminiy vaqt (daqiqa)
            meter_km        REAL,                            -- jonli GPS hisoblagich: bosib o'tilgan masofa (km)
            ozim            INTEGER DEFAULT 0,               -- 1 = manzilni og'zaki aytadi
            cargo           TEXT DEFAULT '',                 -- dostavka: yuk turi
            car_type        TEXT DEFAULT '',                 -- dostavka: yengil/katta yuk
            note            TEXT DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'pending', -- pending|accepted|completed|canceled
            driver_id       INTEGER,                         -- qabul qilgan haydovchi
            created_at      INTEGER NOT NULL,
            accepted_at     INTEGER,
            FOREIGN KEY(customer_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_inbox_tg       ON media_inbox(tg_id);
        CREATE INDEX IF NOT EXISTS idx_users_tg       ON users(tg_id);
        CREATE INDEX IF NOT EXISTS idx_biz_user       ON businesses(user_id);
        CREATE INDEX IF NOT EXISTS idx_item_groups_biz ON item_groups(business_id, created_at);
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
        CREATE INDEX IF NOT EXISTS idx_drivers_user   ON drivers(user_id);
        """
    )
    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    """Eski bazaga yetishmayotgan ustun va jadvallarni xavfsiz qo'shadi (ma'lumot yo'qolmaydi)."""
    # Mahsulot/xizmat guruhlari — v1379. CASCADE qo'ymaymiz: guruh o'chsa, tovarlar Guruhsizga o'tadi.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS item_groups(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            kind TEXT DEFAULT 'product',
            created_at INTEGER NOT NULL
        )"""
    )
    icols = [r["name"] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    if "group_id" not in icols:
        # Eski mahsulotlar avtomatik Guruhsiz bo'lib qolishi uchun NULL ustun qo'shamiz.
        conn.execute("ALTER TABLE items ADD COLUMN group_id INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_item_groups_biz ON item_groups(business_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_items_group ON items(group_id)")

    # Taxi haydovchilari — v1383
    conn.execute(
        """CREATE TABLE IF NOT EXISTS drivers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            phone TEXT DEFAULT '',
            car_model TEXT DEFAULT '',
            car_color TEXT DEFAULT '',
            car_plate TEXT DEFAULT '',
            service TEXT DEFAULT 'taxi',
            available INTEGER DEFAULT 1,
            rating_sum INTEGER DEFAULT 0,
            rating_cnt INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at INTEGER NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drivers_user ON drivers(user_id)")

    # Taxi zakazlari — v1384
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rides(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'taxi',
            from_addr TEXT DEFAULT '',
            to_addr TEXT DEFAULT '',
            from_lat REAL,
            from_lng REAL,
            to_lat REAL,
            to_lng REAL,
            dist_km REAL,
            dur_min INTEGER,
            meter_km REAL,
            ozim INTEGER DEFAULT 0,
            cargo TEXT DEFAULT '',
            car_type TEXT DEFAULT '',
            note TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            driver_id INTEGER,
            created_at INTEGER NOT NULL,
            accepted_at INTEGER
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(status, kind, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rides_customer ON rides(customer_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rides_driver ON rides(driver_id, status)")
    # rides: xaritadan koordinata ustunlari — v1386 (eski jadvalga xavfsiz qo'shamiz)
    rcols = [r["name"] for r in conn.execute("PRAGMA table_info(rides)").fetchall()]
    for _c, _t in (("from_lat", "REAL"), ("from_lng", "REAL"), ("to_lat", "REAL"),
                   ("to_lng", "REAL"), ("dist_km", "REAL"), ("dur_min", "INTEGER"),
                   ("meter_km", "REAL")):
        if _c not in rcols:
            conn.execute("ALTER TABLE rides ADD COLUMN %s %s" % (_c, _t))

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
            media_type        TEXT DEFAULT 'text',   -- 'text' | 'photo'
            media_url         TEXT DEFAULT '',       -- rasm server manzili
            file_name         TEXT DEFAULT '',       -- serverdagi fayl nomi
            reply_to_id       INTEGER,               -- qaysi xabarga javob
            edited_at         INTEGER DEFAULT 0,     -- tahrirlangan vaqt
            deleted_at        INTEGER DEFAULT 0,     -- o'chirilgan vaqt
            is_deleted        INTEGER DEFAULT 0,     -- xavfsiz o'chirish belgisi
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
    if "media_type" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN media_type TEXT DEFAULT 'text'")
    if "media_url" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN media_url TEXT DEFAULT ''")
    if "file_name" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN file_name TEXT DEFAULT ''")
    if "reply_to_id" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN reply_to_id INTEGER")
    if "edited_at" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN edited_at INTEGER DEFAULT 0")
    if "deleted_at" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN deleted_at INTEGER DEFAULT 0")
    if "is_deleted" not in mcols:
        conn.execute("ALTER TABLE messages ADD COLUMN is_deleted INTEGER DEFAULT 0")
    # Eski xabarlar user -> user deb belgilab qo'yiladi, ma'lumot yo'qolmaydi.
    conn.execute("UPDATE messages SET sender_kind='user' WHERE sender_kind IS NULL OR sender_kind=''")
    conn.execute("UPDATE messages SET receiver_kind='user' WHERE receiver_kind IS NULL OR receiver_kind=''")
    conn.execute("UPDATE messages SET sender_actor_id=sender_id WHERE sender_actor_id IS NULL")
    conn.execute("UPDATE messages SET receiver_actor_id=receiver_id WHERE receiver_actor_id IS NULL")
    conn.execute("UPDATE messages SET media_type='text' WHERE media_type IS NULL OR media_type=''")
    conn.execute("UPDATE messages SET media_url='' WHERE media_url IS NULL")
    conn.execute("UPDATE messages SET file_name='' WHERE file_name IS NULL")
    conn.execute("UPDATE messages SET edited_at=0 WHERE edited_at IS NULL")
    conn.execute("UPDATE messages SET deleted_at=0 WHERE deleted_at IS NULL")
    conn.execute("UPDATE messages SET is_deleted=0 WHERE is_deleted IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_pair ON messages(sender_id, receiver_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_actor_pair ON messages(sender_kind, sender_actor_id, receiver_kind, receiver_actor_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_receiver_actor ON messages(receiver_kind, receiver_actor_id, is_read)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_reply ON messages(reply_to_id)")
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
            delivery_lat       REAL,
            delivery_lng       REAL,
            qty                INTEGER DEFAULT 1,
            status             TEXT DEFAULT 'new',
            created_at         INTEGER NOT NULL,
            updated_at         INTEGER NOT NULL,
            provider_seen_at   INTEGER DEFAULT 0,
            customer_seen_at   INTEGER DEFAULT 0
        )"""
    )
    ocols = [r["name"] for r in conn.execute("PRAGMA table_info(orders)").fetchall()]
    if "order_type" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN order_type TEXT DEFAULT 'delivery'")
    if "address" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN address TEXT DEFAULT ''")
    if "desired_time" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN desired_time TEXT DEFAULT ''")
    if "delivery_lat" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN delivery_lat REAL")
    if "delivery_lng" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN delivery_lng REAL")
    if "provider_seen_at" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN provider_seen_at INTEGER DEFAULT 0")
    if "customer_seen_at" not in ocols:
        conn.execute("ALTER TABLE orders ADD COLUMN customer_seen_at INTEGER DEFAULT 0")
    conn.execute("UPDATE orders SET order_type='delivery' WHERE order_type IS NULL OR order_type=''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_kind, customer_actor_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_provider ON orders(provider_kind, provider_actor_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_provider_seen ON orders(provider_kind, provider_actor_id, provider_seen_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer_seen ON orders(customer_kind, customer_actor_id, customer_seen_at)")
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

    conn.execute(
        """CREATE TABLE IF NOT EXISTS order_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        INTEGER NOT NULL,
            sender_kind     TEXT NOT NULL DEFAULT 'user',
            sender_actor_id INTEGER NOT NULL,
            sender_user_id  INTEGER NOT NULL,
            text            TEXT DEFAULT '',
            media_type      TEXT DEFAULT 'text',
            media_url       TEXT DEFAULT '',
            file_name       TEXT DEFAULT '',
            reply_to_id     INTEGER,
            edited_at       INTEGER DEFAULT 0,
            deleted_at      INTEGER DEFAULT 0,
            is_deleted      INTEGER DEFAULT 0,
            created_at      INTEGER NOT NULL
        )"""
    )
    omcols = [r["name"] for r in conn.execute("PRAGMA table_info(order_messages)").fetchall()]
    if "media_type" not in omcols:
        conn.execute("ALTER TABLE order_messages ADD COLUMN media_type TEXT DEFAULT 'text'")
    if "media_url" not in omcols:
        conn.execute("ALTER TABLE order_messages ADD COLUMN media_url TEXT DEFAULT ''")
    if "file_name" not in omcols:
        conn.execute("ALTER TABLE order_messages ADD COLUMN file_name TEXT DEFAULT ''")
    if "reply_to_id" not in omcols:
        conn.execute("ALTER TABLE order_messages ADD COLUMN reply_to_id INTEGER")
    if "edited_at" not in omcols:
        conn.execute("ALTER TABLE order_messages ADD COLUMN edited_at INTEGER DEFAULT 0")
    if "deleted_at" not in omcols:
        conn.execute("ALTER TABLE order_messages ADD COLUMN deleted_at INTEGER DEFAULT 0")
    if "is_deleted" not in omcols:
        conn.execute("ALTER TABLE order_messages ADD COLUMN is_deleted INTEGER DEFAULT 0")
    conn.execute("UPDATE order_messages SET media_type='text' WHERE media_type IS NULL OR media_type=''")
    conn.execute("UPDATE order_messages SET edited_at=0 WHERE edited_at IS NULL")
    conn.execute("UPDATE order_messages SET deleted_at=0 WHERE deleted_at IS NULL")
    conn.execute("UPDATE order_messages SET is_deleted=0 WHERE is_deleted IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_order_messages_order ON order_messages(order_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_order_messages_sender ON order_messages(sender_kind, sender_actor_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_order_messages_reply ON order_messages(reply_to_id)")
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

    # --- v1395: To'liq matnli qidiruv (FTS5) — nom/sarlavha alohida ustun ---
    # Har tur uchun: 'name' ustuni (asosiy nom/sarlavha) + 'body' ustuni (qolgan matn).
    # bm25 tartiblashda nomga ko'proq og'irlik beriladi (api.py). Indeks avtomatik sinxron.
    def _canon_expr(inner):
        expr = "LOWER(" + inner + ")"
        for a in ("'", "\u2019", "\u2018", "`", "\u02bb", "\u02bc"):
            expr = "REPLACE(" + expr + ", '" + a.replace("'", "''") + "', '')"
        return expr

    def _concat(prefix, fields):
        return " || ' ' || ".join("COALESCE(" + prefix + f + ",'')" for f in fields)

    def _setup_fts(table, title_field, body_fields, tag, id_col="id"):
        fts = table + "_fts"
        # Eski sxema (bitta 'txt' ustun) bo'lsa qayta quramiz (indeks manbadan tiklanadi)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(" + fts + ")").fetchall()]
        if cols and cols != ["name", "body"]:
            conn.execute("DROP TABLE IF EXISTS " + fts)
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS " + fts + " USING fts5(name, body)")
        for suf in ("ai", "ad", "au"):
            conn.execute("DROP TRIGGER IF EXISTS " + tag + "_fts_" + suf)
        tval = lambda pfx: _canon_expr("COALESCE(" + pfx + title_field + ",'')")
        bval = lambda pfx: _canon_expr(_concat(pfx, body_fields))
        conn.execute("CREATE TRIGGER " + tag + "_fts_ai AFTER INSERT ON " + table + " BEGIN "
                     "INSERT INTO " + fts + "(rowid, name, body) VALUES(new." + id_col + ", "
                     + tval("new.") + ", " + bval("new.") + "); END")
        conn.execute("CREATE TRIGGER " + tag + "_fts_ad AFTER DELETE ON " + table + " BEGIN "
                     "DELETE FROM " + fts + " WHERE rowid = old." + id_col + "; END")
        conn.execute("CREATE TRIGGER " + tag + "_fts_au AFTER UPDATE ON " + table + " BEGIN "
                     "DELETE FROM " + fts + " WHERE rowid = old." + id_col + "; "
                     "INSERT INTO " + fts + "(rowid, name, body) VALUES(new." + id_col + ", "
                     + tval("new.") + ", " + bval("new.") + "); END")
        if conn.execute("SELECT COUNT(*) FROM " + fts).fetchone()[0] == 0:
            conn.execute("INSERT INTO " + fts + "(rowid, name, body) SELECT " + id_col + ", "
                         + tval("") + ", " + bval("") + " FROM " + table)

    _setup_fts("businesses", "name", ["yon", "tur", "descr", "address", "phone", "telegram", "work_hours"], "biz")
    _setup_fts("listings", "title", ["cat", "price", "descr", "address"], "lst")
