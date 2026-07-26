# Ko‘prik v1620 — desktop maketni to‘g‘rilash

**Talab:** desktop bosh sahifa dastlabki web maketga mos ko‘rinsin: hero matni kesilmasin, headerda takroriy qidiruv bo‘lmasin, reklama xaritadan keyin tursin va takliflar undan keyin ixcham ko‘rinsin. E’lonlar alohida oynada qoladi.

**Qabul mezoni:** desktop header faqat logo, `Bosh sahifa / E’lonlar`, manzil, savat, taxi, tema va kabinetni ko‘rsatadi. Hero va xarita kamida 430 px balandlikda; hero qidiruvida qidiruv hamda joylashuv maydoni bor. Birinchi demo reklama mebel/divan banneri bo‘ladi. Reklama hero ostida, 20 ta taklif reklama ostida chiqadi. Desktop taklif kartalari gorizontal va aylanishi 150 soniya; mobil karusel 68 soniyaligicha qoladi.

**Test:** `test_web_home_frontend_contract.py` elementlar tartibi, hero kesilmasligi, headerdagi ortiqcha qidiruvning yashirilishi, sofa banneri va desktop karusel tezligini tekshiradi. To‘liq regressiya eski cheklovlarni ham tekshiradi.
