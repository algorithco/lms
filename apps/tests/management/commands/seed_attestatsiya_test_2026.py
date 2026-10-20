"""
Django Management Command: seed_attestatsiya_test_2026

Seeds the 50-question Official Attestation Diagnostic Exam 2026
("Ona tili va Adabiyot — Rasmiy Attestatsiya Diagnostika 2026"):
- 1–35: Mutaxassislik fani (Ona tili va adabiyot)
- 36–40: Kasbiy standart (O'qituvchi kompetensiyalari)
- 41–50: Pedagogik mahorat va metodika
- Reading Passages:
    1) "Dunyo tillari haqida qiziqarli ma'lumotlar" (Q1–5)
    2) "Metin va uning ota-onasi haqida hikoya (Badiiy matn)" (Q21–25)
- Full AI explanation for every question.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import Category, Course
from apps.tests.models import (
    Choice,
    ExamScoringProfile,
    ExamSection,
    Question,
    ReadingPassage,
    Test,
)

User = get_user_model()

PASSAGE_1_TITLE = "Dunyo tillari haqida qiziqarli ma'lumotlar"
PASSAGE_1_CONTENT = """DUNYO TILLARI HAQIDA QIZIQARLI MA’LUMOTLAR

I
Dunyoda so‘z jihatidan eng badavlat til arab va ingliz tillari hisoblanadi. Ingliz tili hisobida ikki yarim milliondan ortiq, arab tili hisobida esa uch yarim milliondan ortiq lug‘at boyligi bor. O‘zbek tili zaxirasi taxminan 1 400 000 – 1 600 000 atrofida so‘zga ega ekan.
Bu ma’lumotlar, albatta, ijtimoiy sohalarga nisbatan olingan, xolos. Tilshunoslik fanidan ma’lumki, qaysi tilda sinonimlar – ma’nodosh so‘zlar ko‘p bo‘lsa, o‘sha til eng boy til; shuningdek, qaysi tilda shakldoshlar – omonim so‘zlar ko‘p bo‘lsa, o‘sha til kambag‘al tillar sirasiga kiradi, deya yuritiladi.(1) Masalan, shimoliy qutbda yashaydigan eskimos qabilasiga mansub millat tilida „qor“ so‘zining 20 xil sinonimi mavjud. Arab tilida esa „cho‘l“ so‘zining 100 dan ortiq varianti bor.

II
Boshqa tillarni o’rganish ilmiy jihatdan qiyin bo’lsa-da, ularni o’rganish orqali o’zga davlat madaniyatini ham o’rganish mumkin. Qiyinlik jihatdan xitoy tili 87 mingdan ortiq iyeroglifni qamrab oladi. Ammo kundalik hayotda xitoyliklar ulardan faqat 6 mingtasini ishlatadi. Fin tili esa o‘rganilishi eng oson til. Unda so‘zlar qanday eshitilsa, shunday yoziladi. Grammatikasi ingliz tilinikidan ham murakkabroq, kelishiklar soni 15 taga yetadi.(2)

III
Yer kurrasi bo‘ylab eng keng tarqalgan til ispan tili hisoblanadi. Ispan tilining bu qadar ommalashib ketishiga, avvalo, mashhur sayyohlar, dengiz qaroqchilari va ispaniyalik mustamlakachilar sabab bo‘lib qolgan (3). Hatto AQSHning 50 ta shtatidan 23 tasida davlat tili ispan tili hisoblanadi.

IV
Yevropalik shifokorlar til o‘rganish miyani 15 yoshga yoshartirishi mumkinligini aniqlashdi. Keksalikda bu qarish jarayonini sekinlashtirilishiga va xotirani mustahkamlashiga yordam beradi.(4)
Har bir til o‘ziga xos madaniyatni, tarixni va fikrlash tarzini ifodalaydi. Yangi tillarni o‘rganish nafaqat bilimimizni kengaytiradi, balki boshqa madaniyatlarni tushunishimizga ham yordam beradi. Shu sababli, tillarni o‘rganish va esda saqlash juda muhim jarayondir.

(M. Bobojonov)"""

PASSAGE_2_TITLE = "Metin va uning ota-onasi haqida hikoya (Badiiy matn)"
PASSAGE_2_CONTENT = """Metin va uning ota-onasi haqidagi o'tkir satirik hikoya (Badiiy matn)

Bu xotinning sochi ko'kimtir rangga bo’yalgan bo'lsa ham, peshonasiga osilib tushgan uch tutami oqish ko‘rinardi. Ko'zidan oqqan yosh betidagi bo‘yog‘ini chaplashtirib yuborgan. Ich ko‘ylagining bog'ichi yaponcha ko‘ylakning chap yelkasidan osilib tushgan.
U shu alpozda hovliqib politsiya bo'limiga kirib keldi: “Bolaginamdan ayrilib qoldim! Yolg'izimni olib qochibdi! Voy-dod, yordam bering”.
- Kim o‘g‘irladi? - deb so'radi undan komissar. 
- Erim o‘g‘irladi, komissar to‘ra, yashamagur erim! Uning irkit yuzidan ko‘z yoshi tinmay dumalab turibdi. U eri bilan qo‘ydi-chiqdi bo'lganini, ajralish haqida sudga ariza berganini, eri besh yashar o‘g‘li Metinni olib qochganini yig‘lab gapirib berdi. O‘g‘ilginamni topib bering, komissar to’ra. Bolaginam u muttahamning qo‘lida xarob bo'ladi! Uning gapdon xotinligi bilinib turibdi, o‘zi ham rosa shallaqiga o‘xshaydi.
Komissar uni tinchlantirib, kursiga o‘tqazgandan keyin erining turar joyini surishtirdi. Oradan ko‘p o‘tmay, ikki politsiyachi bilan bir kishi va besh yoshlardagi bola ichkari kirishdi. Boyagi xotin bolani ko‘rishi bilan o‘zini unga tashladi, ammo eri ham anoyi emas ekan, bo‘sh kelmadi. Er-xotin Metinni ikki qo‘lidan ushlab, ikki tomonga tortqilay ketishdi. Uy ichi bolaning dodlab yig‘laganidan, er-xotinning qiy-chuvidan to’s-to’polon bo‘lib ketdi. Metinni ajratib olishga politsiyachilarning kuchi yetmadi. Unisi u yoqqa, bunisi bu yoqqa tortaverganidan bolaning qo‘li chiqdi-yu, otasi qo'yib yubordi. Xotin bolaga bir hamla qilib, uni qo‘ltig‘idan oldi-da, ko‘chaga qochdi. Eri orqasidan quvlamoqchi bo‘lib bir silkingan edi, politsiyachilar ushlab qolishdi.
- Komissar afandim, - dedi u, - xotinimning kimligini bilmaysiz. Mening maqsadim o‘g‘limni yurtga foydali odam qilib tarbiyalash. Bu xotinning qo'lida qolsa, tarbiyasi buzilib ketadi.
Komissar javob berdi: 
- Bolaning yoshi beshda ekan, u onasining qo‘lida qolishi kerak.
- Axir, bu mumkin emas-ku. Sud ham bolani menga hukm qiladi. Nega deganda onasi...
U, xotini yengiloyoq bo'lganligi uchun politsiya qo‘liga tushganligini, bunaqa xotinga bola tarbiyasini ishonib bo'lmasligini aytdi.
Oradan o‘n besh kun o‘tdi. Er-xotin bu gal kasalxonaning oldida janjallashib qolishdi. Onasi qo'li chiqqan Metinni kasalxonadan olib chiqayotganda, eri kelib qolib bir hamla bilan bolani olib qochdi. Xotin ham kalxatdek unga tashlandi. Metinning bir qo'li taxtakachlanganligi uchun ona oyog‘idan, ota esa sog’ qo’lidan tortardi. Bu gal bolaning boshqa joyi mayib bo'ldi, chap qo‘li yelkasidan chiqib ketdi. Olishuvda ota ustun keldi. U og‘riq azobidan chinqirib yig'layotgan o‘g‘lini sudraganicha o‘zini tor ko‘chaga urdi. Endi bola bechoraning ikkala qo‘li ham mayib bo‘ldi. Lekin ota shunisiga ham rozi edi:
- Bu xotinning tarbiyasini olgandan ko‘ra, bolamning bir umr mayib bo‘lgani yaxshi.
Oradan bir oy o‘tdi. Kunlarning birida kechqurun ko‘cha yuzida mashina to‘xtadi. Mashinadan tushgan ayol ko'chada o‘ynab yurgan bolalarning oldiga yugurib keldi-da, Metinga yopishdi. Lekin shu zahotiyoq qayerdandir bolaning dadasi paydo bo‘la qoldi.
Bola yana arosatda qoldi, uning dod-faryodini eshitib odamlar to‘plandi.
- Bola bechorani muncha qiynaysiz, xonim, axir uni o’ldirib qo‘yasiz-ku, - deyishdi yig‘ilganlar.
- Shu sullohning uyida qolib rasvo bo‘lgandan ko‘ra, shu yerda o'lgani yaxshi! - deb qichqirardi onasi zo‘r berib bolaning bir oyog‘idan tortar ekan. Metin-ku o'lgani yo‘q, lekin olishuvda er-xotin uning ikki oyog’idan ikki tomonga cho'zib tortgani uchun avvaliga uning ishtoni, keyin choti yirtildi. Ona bolani bag‘riga bosib mashinaga solib qochdi. Metin bir oy kasalxonada yotib chiqdi. Ona qo'ltiqtayoqda chiqqan o‘g‘lini suyub bag‘riga bosdi.
- Bo’taginam, - dedi onasi, - o‘zim xor bo'lib yursam ham, seni, albatta odam qilaman.
Sud er-xotinning ajralish haqidagi arizasini ko‘rayotgan kuni zalda to’polon ko‘tarildi. Xotin bolani olib qochgan erining orqasidan quvlab qoldi. Naq zinaga yetganida u eriga changal solib, bolani undan yulib oldi. Yulib oldi-yu, shu mahal oyog‘i chalishib ketib, qo'lidagi Metin bilan birga zinadan dumalab tushdi. Boshi yorilgan bola hushidan ketdi. Xotin o'rnidan tura solib, o’g‘lini bag'riga bosganicha eshikka yugurdi. Ko'chaga yugurib chiqishi bilan orqasidan eri yetib keldi. Biri bolaning boshidan, ikkinchisi oyog'idan o‘ziga tortdi. Hali ham hushiga kelmagan Metin og‘riq azobini sezmas edi. 
- Bolaginamni senga bermayman!
- Ko‘raman bermaganingni! 
Politsiya o‘rtaga tushdi. Oxiri Metinni otasi olib ketdi. Uzoq davolanishdan keyin Metin tuzalib chiqdi. Ba’zi jarohatlarni hisobga olmaganda, bola sog‘ edi. Ota-ona o'rtasida bo'lib o'tgan ikki olishuvda uning ikki qo‘li mayib bo‘ldi.
Er-xotinning uchinchi to’qnashuvida Metinning oyog‘i sinib, taxtakachlandi, singan oyoq narigisidan uch santimetr kalta bo‘lib qoldi. Ota-onaning ilgarigi jamiki olishuvlari keyingisining oldida holva edi. Boshi bilan zinadan yumalagan bola bir ko‘zidan ajraldi, o‘zi esa butunlay telba bo‘lib qoldi. Sud bolani onaga hukm qildi. Ota hukm ustidan shikoyat yozdi, keyin natijasini kutib o‘tirmay, o‘g‘lini sobiq xotinining uyidan olib qochdi. Ammo oxirgi paytda ishi yurishmay qoldi. U ota-onasini ajratolmay qolgan Metinni uyiga olib kiray deb turganida, orqadan xotini yetib keldi. Yarim kechada qiy-chuv boshlandi. Bechora Metin bir necha marta qo'ldan qo‘lga o'tdi. Janjalni eshitib, ko'cha qorovuli bilan politsiyachi yugurib keldi.
- Ovunchog'imni bu zolimning qo'lidan olib bering! - ularga yolvordi xotin. - Men uni katta odam qilib tarbiyalayman. 
Metin esa ho'ngrab yig'lardi. 
- Voy sharmanda-yey, men uni vatanim uchun tarbiyalayman desam bermaydi-ya, - pishillaydi ota xotinining qo'lidagi bolani bo'ynidan tortib. Bu suronda quloqdan ajrab, qovurg'asi singan Metin onasida qoladigan bo‘ldi. Biroq onaning quvonchi ko‘pga cho'zilmadi. Oliy sud otaning da’volarini to‘g‘ri deb topib, bolani unga hukm qilib berdi. U politsiyaning yordami bilan Metinni qaytarib oldi. Ochig'ini aytganda, qaytarib oldi deyish unchalik to‘g‘ri emas. Bolani ikkala mayib qo'lidan mahkam ushlab olgan ona dod soldi: 
- Voydod, o'ligimni olsang ham, bolamni ololmaysan. Sen buni rasvo qilasan! 
- Qo‘yib yubor deyman, shallaqi! - bo‘sh kelmadi ota ham. - Qo'yib yubor buni, men uni odam qilaman. 
Xayriyat, politsiya o'rtaga tushdi, bo'lmasa bolani onasining qo‘lidan tortib ololmasdi.
***
Metin uchun bo'lgan tortishuv nihoyat tugadi. Metin janjal-suronda na boshidan va na oyog'idan ajradi, na u tarvuzning ikki pallasiday bo'linib, yarmi otada, yarmi onada qoldi. Ikki o'rtadagi tortishuv uning olamdan ko‘z yumishi bilan poyoniga yetdi. Ota, vatanga munosib farzand tarbiyalab berish niyatida boshqatdan uylandi. Ona esa hozir og'iroyoq - bunisini, albatta katta odam qilib tarbiyalaydi."""

QUESTIONS_DATA = [
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1"},
            {"is_correct": False, "letter": "B", "text": "2"},
            {"is_correct": False, "letter": "C", "text": "3"},
            {"is_correct": True, "letter": "D", "text": "4"},
        ],
        "explanation": "Matndagi 4-jumlada 'qarish jarayonini sekinlashtirilishiga' birikmasida ortiqcha majhul nisbat "
        "qo'shimchasi (-il) qo'llangan. O'timli fe'l bilan boshqarilganda 'qarish jarayonini "
        "sekinlashtirishiga' shaklida aniq nisbatda qo'llanishi kerak edi. Shuning uchun 4-jumlada "
        "so'z/qo'shimcha qo'llash bilan bog'liq uslubiy xatolik mavjud.",
        "position": 1,
        "reading_passage_order": 1,
        "section_code": "MUTAXASSISLIK",
        "text": "Ajratib ko‘rsatilgan qaysi jumlada so‘z yoki qo‘shimcha qo‘llash bilan bog‘liq\n"
        "uslubiy xatolik mavjud?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "I qismda"},
            {"is_correct": False, "letter": "B", "text": "II qismda"},
            {"is_correct": False, "letter": "C", "text": "III qismda"},
            {"is_correct": True, "letter": "D", "text": "IV qismda"},
        ],
        "explanation": "Matnning II qismida 'ularni o'rganish orqali o'zga davlat madaniyatini ham o'rganish mumkin' "
        "deb aytilgan bo'lsa, IV qismda 'boshqa madaniyatlarni tushunishimizga ham yordam beradi' deb "
        "xuddi shu fikr takroran keltirilgan. Mazmuniy takror IV qismda uchraydi.",
        "position": 2,
        "reading_passage_order": 1,
        "section_code": "MUTAXASSISLIK",
        "text": "Matn qismlari o‘rtasidagi mazmuniy bog‘liqlikka ko‘ra takroriy fikr qaysi\nqismda uchraydi?",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Shimoliy qutbda yashaydigan eskimos qabilasiga mansub millat tili kambagʻal\n"
                "tillar sirasiga kiradi",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Ingliz tilida ikki yarim milliondan, arab tilida esa uch yarim milliondan ortiq\n"
                "sinonimlar mavjud",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Dunyo boʻylab eng keng tarqalgan til arab tili hisoblanadi",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "Ingliz tilidan ham murakkabroq grammatikaga ega tilni o’rganish oson",
            },
        ],
        "explanation": "Matnning II qismida fin tili haqida 'Fin tili esa o'rganilishi eng oson til... Grammatikasi "
        "ingliz tilinikidan ham murakkabroq' deb keltirilgan. Bu D variantidagi 'Ingliz tilidan ham "
        "murakkabroq grammatikaga ega tilni o’rganish oson' hukmiga to'liq mos keladi.",
        "position": 3,
        "reading_passage_order": 1,
        "section_code": "MUTAXASSISLIK",
        "text": "Matnda aks etgan ma’lumotqaysi qatorda to‘g‘ri keltirilgan?",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Faktlar va fikrlar soni teng",
            },
            {
                "is_correct": True,
                "letter": "B",
                "text": "Faktlar soni fikrlar sonidan ko’p",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Fikrlar soni faktlar sonidan ko’p",
            },
            {"is_correct": False, "letter": "D", "text": "Barchasi fakt hisoblanadi"},
        ],
        "explanation": "1, 2, 4, 5-jumlalar statistik, obyektiv faktlar hisoblanadi (jami 4 ta fakt). 3-jumla esa "
        "'Tillarni o'rganish va saqlash juda muhim jarayondir' — subyektiv fikrdir (1 ta fikr). Demak, "
        "faktlar soni fikrlar sonidan ko'p (4 > 1).",
        "position": 4,
        "reading_passage_order": 1,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidagima’lumotlardan fakt va fikr to‘g‘ri ajratilganjavobni toping.\n"
        "1. Ingliz tili hisobida ikki yarim milliondan ortiq, arab tili hisobida esa uch yarim\n"
        "milliondan ortiq lug‘at boyligi bor.\n"
        "2. O‘zbek tili zaxirasi taxminan 1 400 000 – 1 600 000 atrofida so‘zga ega.\n"
        "3. Tillarni o‘rganish va saqlash juda muhim jarayondir.\n"
        "4. Xitoy tili 87 mingdan ortiq iyeroglifni qamrab oladi.\n"
        "5. Kundalik hayotda xitoyliklar iyerogliflardan faqat 6 mingtasini ishlatadi.",
    },
    {
        "choices": [
            {"is_correct": True, "letter": "A", "text": "3, 2, 1, 4"},
            {"is_correct": False, "letter": "B", "text": "3, 1, 2, 4"},
            {"is_correct": False, "letter": "C", "text": "3, 4, 1, 2"},
            {"is_correct": False, "letter": "D", "text": "3, 4, 2, 1"},
        ],
        "explanation": "Matndagi fikrlarning bayon etilish tartibi: birinchi bo'lib ingliz tili lug'at boyligi (3), "
        "so'ng arab tilida cho'l so'zining variantlari (2), keyin AQSh shtatlarida ispan tili (1) va "
        "nihoyat Yevropa shifokorlarining xulosasi (4) kelgan. To'g'ri tartib: 3, 2, 1, 4.",
        "position": 5,
        "reading_passage_order": 1,
        "section_code": "MUTAXASSISLIK",
        "text": "Matndaaksetganfikrlarni ketma-ket joylashtiring.\n"
        "1. Amerika Qo’shma shtatlarining qariyb yarmida davlat tili ispan tili hisoblanadi.\n"
        "2. Arab tilida bir so‘zning 100 dan ortiq varianti bor.\n"
        "3. Ingliz tilida ikki yarim milliondan ortiq lug’at boyligi mavjud.\n"
        "4. Yevropada shifokorlar til o‘rganish miyani yoshartirishi mumkinligini aniqlashdi.",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1, 3, 4"},
            {"is_correct": False, "letter": "B", "text": "2, 3, 5"},
            {"is_correct": False, "letter": "C", "text": "1, 4"},
            {"is_correct": True, "letter": "D", "text": "barchasi"},
        ],
        "explanation": "Berilgan barcha gaplarda qo'shimchalar talaffuzi bilan imlosida farq bor: 1-gapda -yapti "
        "(-votti), 2-gapda -dir (-di), 3-gapda -cha (-shsha), 4-gapda -cha (-shsha), 5-gapda -gacha "
        "(-kkacha). Barchasida fonetik hodisa aks etgan.",
        "position": 6,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Qaysigapdaqo‘shimchalarning talaffuzi va imlosida farq bor?\n"
        "1. Kimdir yelpib-yelpib barra-barra go‘shtlardan kabob pishiryapti.\n"
        "2. Bir kuni bechora chol qo‘li titrab, osh suzib berilgan kosasini tushirib sindirdi…\n"
        "3. Endi osonlikcha qutulib keta olasan.\n"
        "4. Kuzatishimcha, odamlar gapirayotgan gapning taxminan 30–40 foizi yolg‘on ekan.\n"
        "5. O‘sha tog‘gacha taxminan oltmish kilometr yuramiz.",
    },
    {
        "choices": [
            {"is_correct": True, "letter": "A", "text": "1, 3"},
            {"is_correct": False, "letter": "B", "text": "1, 4"},
            {"is_correct": False, "letter": "C", "text": "1, 2"},
            {"is_correct": False, "letter": "D", "text": "3, 4"},
        ],
        "explanation": "Matnda 'aktiyorlik' so'zida ortiqcha unli tovush qo'llangan (aktyorlik bo'lishi kerak, "
        "1-xatolik), shuningdek 'ishtiyog'im' o'rnida imlo qoidasiga ko'ra asos va qo'shimcha "
        "tutashuvida xatolik yuz bergan (3-xatolik).",
        "position": 7,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidagigapdaqanday turdagi imloviy xatolik(lar) yuz berganini aniqlang.\n"
        "Men shu kino bilan aktiyorlik poydevorini qurdim, desam bo‘ladi. Ilk bora o‘ynagan\n"
        "rolim menga sen aktiyor bo‘lishing kerak, ijodning odamisan, degan fikrni tasdiqlagan\n"
        "3\n"
        "film bo‘lgan. O‘zi yoshlikdan aktyorlikka ishtiyog‘im baland bo‘lgan, shu filmdan\n"
        "so‘ng aktiyorlikni tanlaganman.\n"
        "1) unli va undosh tovushlar bilan bog'liq xatolik;\n"
        "2) chiziqcha qo'llash bilan bog'liq xatolik;\n"
        "3) asos va qo'shimchalar bilan bog'liq xatolik;\n"
        "4) bosh harf qo’llash bilan bog’liq xatolik.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "So‘z yasovchi qo‘shimcha faqat ta’sirida tovush tushishi kuzatiladi",
            },
            {
                "is_correct": True,
                "letter": "B",
                "text": "Lug‘aviy shakl yasovchi ta’sirida faqat ta’sirida tovush tushishi kuzatiladi",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Sintaktik shakl yasovchi ta’sirida fonetik hodisalarning har uchala turi yuz "
                "bergan",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "To‘liqsiz fe’l tarkibida tovush tushishi kuzatiladi",
            },
        ],
        "explanation": "Lug'aviy shakl yasovchi qo'shimchalar ta'sirida faqat tovush tushishi emas, balki tovush "
        "almashishi yoki ortishi ham ro'y berishi mumkin. Matnda ham bu qat'iy cheklov to'g'ri emas, "
        "shuning uchun B hukmi noto'g'ri.",
        "position": 8,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidagigapdafonetik o’zgarishga uchragan so’zlar haqida noto’g’ri hukmni\n"
        "aniqlang.\n"
        "…O‘sha paytlar drama to‘garagiga qatnashardim. Meni dastlab Omon roliga\n"
        "tasdiqlashgan. Oxirida “Shum bola” rolida ham o‘ynab ko‘rsin, deyishgan. Shum bola\n"
        "roli avvalroq Xayrulla Sa’diyev ijrosida tanilgan. Shunda Omon rolini o‘ynagan\n"
        "Saidkarim bilan ikkalamiz ham shum bolani, ham Omonni o‘ynaganmiz. Keyin meni\n"
        "shum bolaga tasdiqlashgan, uni Omon rolida qoldirishgan.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "“ “ ” , - , - “ ” . , “ ” ” .",
            },
            {"is_correct": False, "letter": "B", "text": "“ ” , - : . , “ ” ."},
            {"is_correct": True, "letter": "C", "text": "“ “ ” , - , - . , “ ” ” ."},
            {"is_correct": False, "letter": "D", "text": "“ “ ” , - , - . , ” ."},
        ],
        "explanation": "Qirol nutqi film nomi qo'shtirnoqqa olinadi: “Qirol nutqi”, muallif gapi vergul va tire bilan "
        "ajratiladi (, - deb aytishgandi televizorda, -), so'ngra gap tugagach nuqta va kirish so'zidan "
        "so'ng vergul qo'yiladi. To'g'ri ketma-ketlik C variantida.",
        "position": 9,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Berilgan gapda qo'llanishi lozim bo'lgan tinish belgilari to'g'ri ketma-ketlikda\n"
        "ko'rsatilgan javobni aniqlang.\n"
        "Dramatik sahnalarga boy Qirol nutqi tarixiy filmi deb aytishgandi televizorda Oskar\n"
        "mukofotining to‘rtta nominatsiyasi bo‘yicha g‘oliblikni qo‘lga kiritgan Shuningdek\n"
        "Oltin globus mukofotiga ham loyiq ko‘rilgan",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1, 4"},
            {"is_correct": False, "letter": "B", "text": "2, 5"},
            {"is_correct": True, "letter": "C", "text": "1, 3"},
            {"is_correct": False, "letter": "D", "text": "1, 2"},
        ],
        "explanation": "1-gapda (Gadjet, qurilma – ...) va 3-gapda (Mana shu – ...) tire ega va ot kesim o'rtasida bir "
        "xil punktuatsion qoida asosida qo'yilgan.",
        "position": 10,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Qaysigaplarda tire bir xil punktuatsion qoida asosida qo‘yilgan?\n"
        "1. Gadjet, qurilma – ishimizni oson, qulay qiluvchi smartfon, planshet, aqlli soat kabi\n"
        "ixcham texnik vositalar.\n"
        "2. O‘ndan ortiq jamoaga ovoz kuchaytiruvchi vosita – mikrofon yetkazib berish\n"
        "muammosi tufayli bu holat sodir bo‘lyapti.\n"
        "3. Bir marta “Zakovat” o‘ynagan kishi hali o‘sishi, kitob varaqlashi kerakligini anglab\n"
        "yetadi. Mana shu – eng katta burilish.\n"
        "4. Uchishga qanot kerak, o‘qishga – toqat.\n"
        "5. – Bolalikni nimaga qiyoslaysiz?\n"
        "– Aslida, bolalikni hech narsaga qiyoslab bo‘lmaydi.",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1, 3"},
            {"is_correct": True, "letter": "B", "text": "2, 4"},
            {"is_correct": False, "letter": "C", "text": "1, 2"},
            {"is_correct": False, "letter": "D", "text": "3, 4"},
        ],
        "explanation": "Gap tahlili: lug'aviy shakl yasovchi qo'shimchalar 4 ta va fe'lning aloqa-munosabat shakllari "
        "3 ta to'g'ri ajratilgan variant 2 va 4 bo'lib, B varianti to'g'ri keladi.",
        "position": 11,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbugaptarkibidagi qo'shimchalar soni va turi to'g'ri ko'rsatilgan javobni\n"
        "aniqlang.\n"
        "Ilgari teatrda aktyorlar niqob taqqan. Niqob tomoshabinga qanday obraz turganini\n"
        "anglatgan. Ya’ni u qahramonning rahmdil yoki jahldor, quvnoq yoki g‘amgin holatini\n"
        "tushunish uchun yordam bergan.\n"
        "1. So'z yasovchi qo'shimcha - 4 ta.\n"
        "2. Lug'aviy shakl yasovchi qo'shimcha - 4 ta.\n"
        "3. Ismlarning aloqa-munosabat shakllari - 5 ta.\n"
        "4. Fe'lning aloqa-munosabat shakllari - 3 ta.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Baliqlar o‘ta ziyrak bo‘lib, xavfli xo‘rakni eslab qolishadi.",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Men bu hovuzning sut bilan to‘ldirilishini xohlayman.",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Bugunning chorasini ko'rib, erta uchun ehtiyoji qolmagan kishi aqllidir.",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "San'at - boshdan kechirilgan tuyg'ularning boshqalar bilan bo'lishish usulidir.",
            },
        ],
        "explanation": "D variantida 'boshdan kechirilgan tuyg'ularning boshqalar bilan bo'lishish usulidir' jumlasi "
        "grammatik-uslubiy xatodir. 'Tuyg'ularni boshqalar bilan bo'lishish' (tushum kelishigi) "
        "qo'llanishi lozim edi.",
        "position": 12,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Qaysijavobdaso'z yoki qo‘shimcha qo‘llash bilan bog‘liq uslubiy xatolik\nmavjud?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1 va 3"},
            {"is_correct": True, "letter": "B", "text": "Faqat 2"},
            {"is_correct": False, "letter": "C", "text": "Faqat 3"},
            {"is_correct": False, "letter": "D", "text": "Faqat 4"},
        ],
        "explanation": "Parchada 'kul bo'ldi' deyilgandan keyin 'yonib jizg'anak bo'ldi' deb aytilishi fikrlar "
        "ketma-ketligida mantiqiy chalkashlikni keltirib chiqargan. Shuning uchun nutqning mantiqiylik "
        "sifati buzilgan.",
        "position": 13,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbuparchada nutqning qaysi kommunikativ sifat(lar)i buzilgan?\n"
        "Eh, qancha chilvir u? Yonib kul bo‘ldi-ku o‘sha chilvirlar. Hammasi yonib jizg'anak\n"
        "bo‘ldi-ku.\n"
        "1. Nutqning aniqligi.\n"
        "2. Nutqning mantiqiyligi.\n"
        "3. Nutqning to’g’riligi.\n"
        "4. Nutqning jo’yaliligi.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Faqat til oldi jarangli undoshlardan iborat so’z mavjud.",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Faqat til oldi jarangsiz undoshlardan iborat so’z mavjud.",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "Faqat til oldi sirg‘aluvchilardan tashkil topgan so‘z mavjud.",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Bo‘g‘iz undoshi mavjud so‘zlarda jarangli undoshlar mavjud emas",
            },
        ],
        "explanation": "'sir' so'zidagi 's' va 'r' tovushlari til oldi sirg'aluvchi undoshlaridir. Demak, so'z faqat "
        "til oldi sirg'aluvchilardan tashkil topgan.",
        "position": 14,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbugaphaqidagi to'g'ri hukmni aniqlang.\n"
        "Hunar o'rgan, chunki hunarda ko'p sir,\n"
        "Yopiq eshiklarni ochar birma-bir.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Metonimiya asosida ma’nosi ko’chgan bo’lib, faqat jarangli undoshlardan iborat",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Metafora asosida ma’nosi ko’chgan bo’lib, o’z shakldoshiga ega",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Vazifadoshlik asosida ma’nosi ko’chgan bo’lib, undalma vazifasini bajargan",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "Sinekdoxa asosida ma’nosi ko’chgan bo’lib, gap bo’laklari bilan aloqaga\n"
                "kirishmagan",
            },
        ],
        "explanation": "'Jigarim' so'zi inson ma'nosida sinekdoxa (a'zo orqali butun shaxs) usulida ko'chgan va gapda "
        "undalma bo'lib kelgani bois gap bo'laklari bilan sintaktik aloqaga kirishmagan.",
        "position": 15,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ajratib ko’rsatilgan so’z haqida to’g’ri hukmni aniqlang.\n"
        "Sen yetim emassan,\n"
        "Tinchlan, jigarim.\n"
        "Quyoshday mehribon\n"
        "5\n"
        "Vataning – onang,",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Tuzilishiga ko’ra ravishlarning 2 turi qatnashgan",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Tub va yasama sifatlar ishtirok etgan",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Olmoshning ma’nosiga ko’ra 2 turi qatnashgan",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "Affiksatsiya va kompozitsiya usulida yasalgan fe’llar ishtirok etgan",
            },
        ],
        "explanation": "Ushbu she'riy parchada kompozitsiya usulida (qo'shma) yasalgan fe'l yo'q. 'Xabar berar' "
        "qo'shma fe'l emas, analitik / ko'makchi fe'lli shakl hisoblanadi. D javobi noto'g'ri "
        "izohlangan.",
        "position": 16,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbu gapda qatnashgan so’z turkumlari haqidagi hukm(lar)dan\n"
        "NOTO'G'RIizohlangan?\n"
        "Istar yana koʻngillar sharob,\n"
        "Chanqab seryog‘ ul qiyma etdan.\n"
        "Qoʻng‘iroqli soat-chi, shu tob\n"
        "Xabar berar yangi baletdan.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Otlashgan sifatdosh kesim vazifasini bajargan",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Ravishdosh hol va kesim vazifasini bajargan",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Majhul nisbatdagi fe’l ot kesim vazifasini bajargan",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "Ko’makchi fe’lli so’z qo’shilmasi faqat bosh bo’lak vazifasida kelgan",
            },
        ],
        "explanation": "Parchadagi ko'makchi fe'lli so'z qo'shilmalari ('ochilib yotar', 'osilib turardi') faqat kesim "
        "(bosh bo'lak) vazifasida kelgan. Shuning uchun D hukmi to'g'ri.",
        "position": 17,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Parchada ishtirok etgan fe'llar haqida to’g’ri hukmni aniqlang.\n"
        "Hovlimizda sara gullar qulf urib ochilib yotar, marmar polli va keng oynali xonalarda\n"
        "eng qimmat gilamlar to‘shalgan, shiftda billur qandillar osilib turardi. Birinchi\n"
        "qavatdagi mehmonxonada otamning qirol Nodirshoh bilan tushgan surati bor edi.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Vazifadosh modal so’z ishtirok etgan",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Taqlid so’zdan kompozitsiya usulida fe’l yasalgan",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "His-hayajon undovi ishtirok etgan",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "Vazifadosh ko’makchi qatnashgan",
            },
        ],
        "explanation": "'...haftadan beri' birikmasidagi 'beri' so'zi o'rin-payt munosabatini ifodalovchi vazifadosh "
        "ko'makchidir.",
        "position": 18,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidaberilganparchada mustaqil bo’lmagan so’zlar haqida to’g’ri javobni\n"
        "aniqlang.\n"
        "Afsuski, yaqin ikki haftadan beri ko‘z ochirmayotgan kuzak shamoli yaydoq daraxtlar\n"
        "shoxida chiyillaydi, g‘uvullaydi; tomlarda vishillaydi, yopiq eshik va darchalarga bosh\n"
        "urib uf tortadi.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Mutaxassis Sara Mednik, uyqu kabi ta'sir",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Shug'ullanuvchi mutaxassis, xuddi sakkiz soatlik",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "Ma'lumotni o'zlashtirish, uxlash ta'sir ko'rsatadi",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Mizg'ib olish uchun bir, uyquni o'rganish",
            },
        ],
        "explanation": "'Ma'lumotni o'zlashtirish' boshqaruvli birikma va 'uxlash ta'sir ko'rsatadi' ega hamda "
        "kesimning to'g'ri grammatik birikuvidir.",
        "position": 19,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbugapdagi so’zlarning grammatik jihatdan to’g’ri birikuvini aniqlang.\n"
        "\"Mizg'ib olish uchun bir yoki bir yarim soatlik uxlash ma'lumotni o'zlashtirish\n"
        "xususiyatiga xuddi sakkiz soatlik uyqu kabi ta'sir ko'rsatadi\", - deya ta'kidlaydi uyquni\n"
        "o'rganish bilan shug'ullanuvchi mutaxassis Sara Mednik.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "I, III - bog’lovchisiz qo’shma gap, II - ergash gapli qo’shma gap",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "I, III - bog’langan qo’shma gap, II - sodda gap",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "I - sodda gap, II - ergash gapli qo’shma gap, III - bog’lovchisiz qo’shma gap",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "I, III - sodda gap, II - ergash gapli qo’shma gap",
            },
        ],
        "explanation": "I gap ('Yoshlikda bilgani - toshga yozgani') va III gap ('Go'zal xulq... kalitidir') bitta "
        "grammatik asosga ega sodda gaplar. II gap esa shart ergash gapli qo'shma gap. To'g'ri javob D.",
        "position": 20,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidaberilgangaplarning tuzilish turi bo’yicha to’g’ri guruhlang.\n"
        "I. Yoshlikda bilgani - toshga yozgani.\n"
        "II. Namozlarini o‘qib chiqib qarasalar, tilanchi ham, otlarining egari ham yo‘q ekan.\n"
        "III. Go‘zal xulq va boshqalarga yaxshilik qilish, farzandlarga yaxshi o‘rnak bo‘la olish\n"
        "saodat saroyining kalitidir.",
    },
    {
        "choices": [
            {"is_correct": True, "letter": "A", "text": "“Farzand”"},
            {"is_correct": False, "letter": "B", "text": "“Ona tarbiyasi”"},
            {"is_correct": False, "letter": "C", "text": "“Sud qarori”"},
            {"is_correct": False, "letter": "D", "text": "“Oltin qoida”"},
        ],
        "explanation": "Hikoyada ota-onaning xudbinlik bilan talashishi tufayli qurbon bo'lgan begunoh bola fojiasi "
        "tasvirlangani uchun eng munosib sarlavha — 'Farzand'.",
        "position": 21,
        "reading_passage_order": 2,
        "section_code": "MUTAXASSISLIK",
        "text": "Matnga qanday sarlavha qo’yish mumkinligini aniqlang.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Muallif obrazlar xarakterini ochib berish jonli va ta’sirchan monologlardan\n"
                "foydalangan",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Muallif hikoyaga ixchamlik, aniqlik baxsh etish maqsadida frazeologik "
                "birliklardan\n"
                "unumli foydalangan",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Asar badiiyatini boyitish maqsadida o’xshatish, qiyoslash kabi badiiy tasvir\n"
                "vositalaridan foydalanilgan",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "Muallif hikoya mazmunini o’tkir satira orqali ochib bergan",
            },
        ],
        "explanation": "Hikoya qahramonlarining soxta vatanparvarligi va farzand tarbiyasiga da'vosidagi munofiqlik "
        "o'tkir satira va qora yumor vositasida ochib berilgan.",
        "position": 22,
        "reading_passage_order": 2,
        "section_code": "MUTAXASSISLIK",
        "text": "Muallif uslubiga oid to’g’ri javobni aniqlang",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "2,4 – to’g’ri; 1, 3 – noto’g’ri",
            },
            {
                "is_correct": True,
                "letter": "B",
                "text": "1,2,3 – noto’g’ri; 4 – to’g’ri",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "1 – to’g’ri; 2, 3, 4 – noto’g’ri",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "2,3 – to’g’ri; 1, 4 – noto’g’ri",
            },
        ],
        "explanation": "1, 2 va 3-ta'riflar noto'g'ri, chunki na ota va na ona bolaning sog'lom voyaga yetishi haqida "
        "qayg'urgan; 4-ta'rif to'g'ri (ota o'zini takabburlik bilan faqat tarbiya uchun javobgar deb "
        "hisoblagan).",
        "position": 23,
        "reading_passage_order": 2,
        "section_code": "MUTAXASSISLIK",
        "text": "Matndatasvirlangan obrazlarga berilgan ta’riflarni to’g’ri yoki noto’g’riga\n"
        "ajrating.\n"
        "9\n"
        "1.Ona – hayotdagi haqiqatdan ko’ra o’zining ichki qo’rquvlaridan xavotirga tushgan\n"
        "hamda sud hukmidan norozi bo’lgan qahramon\n"
        "2.Ota – farzandini tarbiyalash yo’lida duch kelgan to’siqlarni yengishga harakat\n"
        "qilayotgan mehribon ota obrazi\n"
        "3.Ona – Metinning sog’lom va tarbiyali bo’lib voyaga yetishini istagani uchun\n"
        "kurashgan qahramon\n"
        "4.Ota – bolasining hayoti uchun emas, uning tarbiyasi uchun o’zini javobgar\n"
        "hisoblagan takabbur inson",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1, 2"},
            {"is_correct": False, "letter": "B", "text": "2, 3"},
            {"is_correct": False, "letter": "C", "text": "3, 4"},
            {"is_correct": True, "letter": "D", "text": "Faqat 4"},
        ],
        "explanation": "Ushbu satirik asar insoniy illatlar, munofiqlik va soxta burch hissi ustidan yozilgan achchiq "
        "hajvdir. Faqat 4-xulosa to'g'ri.",
        "position": 24,
        "reading_passage_order": 2,
        "section_code": "MUTAXASSISLIK",
        "text": "Hikoya haqidagi to’g’ri xulosani aniqlang.\n"
        "1-xulosa. Hikoya inson ruhiyatini ochib beruvchi badiiy tahlilga ega asar hisoblanadi\n"
        "2-xulosa. Insonlarning savodsizligi va o’z huquqlarini bilmasliklari kabi mavzular\n"
        "ko’tarilgan asar .\n"
        "3-xulosa. Hikoyada bolaning hayoti emas, balki kim farzand tarbiyalash uchun\n"
        "qanchalik loyiq ekanligi masalasi ko’tarilgan\n"
        "4-xulosa. Odamlar hayoti, ularning muammolari va insoniy illatlar haqidagi achchiq\n"
        "haqiqatlar hajv ostiga olingan asardir",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Ushbu parchada o’g’lining taqdiridan tashvishlanayotgan mehribon onaning\n"
                "fikrlari tasvirlangan.",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Ushbu parchada bola tarbiyasi eng muhim masala ekanini anglagan hamda bolaga\n"
                "to’g’ri tarbiya berish yo’llarini izlayotgan otaning tashvishli holati bayon "
                "qilingan.",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "Ushbu parchada farzandining hayoti uchun emas, aslida turmush o’rtog’iga qarshi\n"
                "ish tutayotgan ona tasvirlangan.",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Ushbu parchada kishilar o’z fikrlarini mustaqil bildira olmasa, jamiyat ular "
                "ustidan\n"
                "kulishi ifoda etilgan.",
            },
        ],
        "explanation": "Onaning 'Shu sullohning uyida qolib rasvo bo'lgandan ko'ra, shu yerda o'lgani yaxshi!' degan "
        "so'zlari uning asl maqsadi bola taqdiri emas, sobiq eriga nisbatan intiqom va dushmanlik "
        "ekanini ko'rsatadi.",
        "position": 25,
        "reading_passage_order": 2,
        "section_code": "MUTAXASSISLIK",
        "text": "Matndan olingan ushbu parcha yuzasidan bildirilgan to’g’ri hukmni aniqlang.\n"
        "- Bola bechorani muncha qiynaysiz, xonim, axir uni o ’ldirib qo‘yasiz-ku, - deyishdi\n"
        "yig‘ilganlar.\n"
        "- Shu sullohning uyida qolib rasvo bo‘lgandan ko‘ra, shu yerda o'lgani yaxshi! - deb\n"
        "qichqirardi onasi…",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Ushbu parcha Erkin Vohidov qalamiga mansub, sobit – mustahkam; ma’vo –\n"
                "me’yor; sarbon – rahbar; sayyor – harakatlanuvchi",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Ushbu she’r Abdulla Oripov qalamiga mansub sobit – haqiqiy; ma’vo – manzil;\n"
                "sarbon – boshlab boruvchi; sayyor – aylanuvchi",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "Ushbu she’riy parcha Erkin Vohidov qalamiga mansub, sobit – mustahkam; ma’vo\n"
                "– manzil; sarbon – boshlab boruvchi; sayyor – doimo harakatlanuvchi",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Ushbu she’r Iqbol Mirzo qalamiga mansub, sobit – mustahkam; ma’vo – manzil;\n"
                "sarbon – boshlab boruvchi; sayyor – sayyora",
            },
        ],
        "explanation": "Ushbu she'riy parcha Erkin Vohidovning 'Inson' qasidasidan olingan: sobit – mustahkam; ma’vo – "
        "manzil; sarbon – yetaklovchi/boshlab boruvchi; sayyor – harakatlanuvchi.",
        "position": 26,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbushe’riy parcha yuzasidan bildirilgan to’g’ri hukmni aniqlang\n"
        "Sobit-u sayyorada inson o’zing, inson o’zing,\n"
        "Mulki olam ichra bir xoqon o’zing, sulton o’zing.\n"
        "Sobit o’z ma’vosida, sayyor fazo dunyosida,\n"
        "Koinot sahrosida karvon o’zing, sarbon o’zing .\n"
        "10",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Erix Mariya Remarkning “G’arbiy frontda o’zgarish yo’q” asaridan olingan bo’lib,\n"
                "uyiga qaytgan Paulning onasi bilan suhbati aks etgan",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Erkin Vohidov xotiralaridan olingan ushbu fikrlar orqali shoir o’sha davrdagi\n"
                "insonlar turmushi haqida aytib o’tgan",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "Erix Mariya Remarkning “G’arbiy frontda o’zgarish yo’q” asari yozilishi haqidagi\n"
                "xotiralari bayon etilgan",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Antuan de Sent-Ekzyuperining vatanni tark etib, muhojirlikda yashagan yillari\n"
                "haqida xotiralari aks etgan",
            },
        ],
        "explanation": "Erix Mariya Remark Birinchi jahon urushi dahshatlarini boshidan kechirib, o'zining mashhur "
        "'G'arbiy frontda o'zgarish yo'q' romani qanday yaratilgani haqidagi xotiralarini ifodalagan.",
        "position": 27,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyida parchasi keltirilgan asar haqidagi to’g’ri hukmni aniqlang.\n"
        "“O’zimni o’zim tahlil qilish orqali men urush xotiralarimni jonlantirdim… Juda ko’p\n"
        "do’stlarim va tanishlarimda o’zimnikiga o’xshagan holatni kuzatdim. Urush soyasi\n"
        "bizni doim – hatto unutishga harakat qilganimizda ham – ta’qib qilardi. Bir kuni\n"
        "meni qo’limga qalam olib, yozishga majbur qildi”",
    },
    {
        "choices": [
            {"is_correct": True, "letter": "A", "text": "2, 5"},
            {"is_correct": False, "letter": "B", "text": "1, 4"},
            {"is_correct": False, "letter": "C", "text": "2, 3"},
            {"is_correct": False, "letter": "D", "text": "2, 6"},
        ],
        "explanation": "Ushbu tuyuq Lutfiy qalamiga mansub bo'lib (2), ikkinchi misradagi 'yoqila' so'zi o't "
        "yoqmoq/olov ma'nosida ishlatilgan (5). To'g'ri javob 2, 5 (A).",
        "position": 28,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbumisralar haqida to’g’ri ma’lumot berilgan javobni aniqlang\n"
        "Qomatimni necha qoshing yo qila?\n"
        "Necha hajr o’ti jonimda yoqila?\n"
        "G’amza birla to’kti qonim ul sanam,\n"
        "To hinotek qon elina yoqila.\n"
        "1.Janri ruboiy\n"
        "2.Lutfiy qalamiga mansub\n"
        "3.Yig’iq radif qo’llangan\n"
        "4.Navoiy qalamiga mansub\n"
        "5.Ikkinchi misradagi “yoqila” so’zi “yoqmoq” ma’nosida ishlatilgan\n"
        "6.G’amza so’zining ma’nosi – ko’z yosh",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "1-to’g’ri, 2-noto’g’ri, 3-noto’g’ri",
            },
            {
                "is_correct": True,
                "letter": "B",
                "text": "1-noto’g’ri, 2-to’g’ri, 3-to’g’ri",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "1-to’g’ri, 2-to’g’ri, 3-noto’g’ri",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "1-noto’g’ri, 2-noto’g’ri, 3-to’g’ri",
            },
        ],
        "explanation": "1-parcha ('Davlatingning borida / To'y qila ko'r, yor-yor') lirik emas, marosim qo'shig'i "
        "(noto'g'ri). 2 va 3 esa mavsum-marosim qo'shiqlaridir (to'g'ri). Demak: 1-noto'g'ri, "
        "2-to'g'ri, 3-to'g'ri (B).",
        "position": 29,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Xalqog’zaki ijodinamunalari haqidagi izohlarning to’g’ri yoki noto’g’riligini\n"
        "aniqlang.\n"
        "1. Davlatingning borida\n"
        "To’y qila ko’r, yor-yor.\n"
        "Ostonasi tillodan\n"
        "Uy qila ko’r, yor-yor\n"
        "Lirik qo’shiq\n"
        "2.Oq terakmi, ko’k terak? Mavsum-marosim qo’shig’i\n"
        "11\n"
        "Bizdan sizga kim kerak?\n"
        "Oy kerag-u, oy kerak,\n"
        "To’lib oqqan soy kerak.\n"
        "Bizga Maqtov qog’ozi\n"
        "Olgan Hasanboy kerak!\n"
        "3. Boychechagim hillolik,\n"
        "Hamyon-hamyon tillolik.\n"
        "Hamma bozor – bir bozor,\n"
        "Atroflari lolazor.\n"
        "Mavsum-marosim qo’shig’i",
    },
    {
        "choices": [
            {
                "is_correct": True,
                "letter": "A",
                "text": "Ijodkor uch qismdan iborat “Vistavka xususida” asarida ma’rifatparvarlik\n"
                "g’oyalarini ilgari surgan",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Ushbu parcha muallifi o’zining “Maktab”, “Til” kabi she’rlari orqali millatni\n"
                "savodli, ilmli qilib, jaholatdan chiqarishga harakat qilgan",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Arab, fors tillarini yaxshi bilgan ushbu ijodkor Alisher Navoiy, Jomiy va boshqa\n"
                "sharq mumtoz adabiyoti vakillari ijodini sevib mutolaa qilgan",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Ushbu parcha muallifi tomonidan yozilgan “Rohati dil” asari pandnoma asarlar\n"
                "sirasiga kiradi",
            },
        ],
        "explanation": "Ushbu ma'rifatparvarlik misralari muallifi Furqat bo'lib, u uch qismdan iborat mashhur "
        "'Vistavka xususida' asarida taraqqiyot va ilm-ma'rifatni targ'ib qilgan.",
        "position": 30,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbuparchamuallifi haqidagi to’g’ri hukmni aniqlang.\n"
        "Kerak har ilmdan bo’lmak xabardor,\n"
        "Bo’lur har qaysi o’z vaqtida darkor!",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "“Saodat sohili” asaridan olingan bo’lib; qursoq – kichik yoshli bola;",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "“Mening o’grigina bolam” asaridan olingan bo’lib; qursoq – yetimlar;",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "“O’zbeklar” hikoyasidan olingan bo’lib; qursoq – qorin;",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "“Boychechak” hikoyasidan olingan bo’lib; qursoq – hali shakllanmagan bola",
            },
        ],
        "explanation": "Parcha Shukur Xolmirzayevning 'O'zbeklar' hikoyasidan olingan. 'Qursoq' so'zi bu o'rinda "
        "bola/qorin ma'nosida qo'llangan.",
        "position": 31,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidaparchasikeltirilgan asar haqidagi to’g’ri javobni aniqlang.\n"
        "“… Qadrdon, bizda ham bir momo bo’lg’ich edi. Bobomiz bosmachilarning otlariga\n"
        "xashak bergani uchun “”xalq dushmani” deb otilib ketgan, undan qolgan o’n bir\n"
        "qursoqni boqaman deb umrini toq o’tkazgan kampir edi. Ularniyam birin – ketin\n"
        "Yaratganiga topshirib, bizning maymoq ota bilan qolgan…",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "“Tanho qayiq” hikoyasidan olingan ushbu parchada Orol boboning yurtini tashlab\n"
                "ketayotgan insonlarga nisbatan xitobi aks etgan",
            },
            {
                "is_correct": True,
                "letter": "B",
                "text": "“Oqchorloq Jonatan Lingviston” asaridan olingan ushbu parchada kengash\n"
                "qaroridan norozi bo’lgan Jonatanning nutqi aks etgan",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "“Hayotga muhabbat” hikoyasidan olingan ushbu parchada yo’lovchining hayot\n"
                "haqidagi xulosalari aks etgan",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "“Oqchorloq Jonatan Lingviston” asaridan olingan ushbu parchada to’dadan nohaq\n"
                "ayblov bilan quvilgan Fletcher Lindning o’y-fikrlari tasvirlangan",
            },
        ],
        "explanation": "Ushbu parcha Rixard Baxning 'Oqchorloq Jonatan Livingston' asaridan olingan bo'lib, unda to'da "
        "kengashi qaroriga qarshi Jonatanning erkinlik va yuksalish haqidagi xitobi bayon qilingan.",
        "position": 32,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidaparchasikeltirilgan asar haqidagi to’g’ri javobni aniqlang.\n"
        "“ – Beandishalik deysizmi?! – xitob qildi u. – Sizlarga nima bo’ldi, birodarlar?!\n"
        "Hayotning mohiyatini tushunishga urinish, katta maqsadlarga olib boradigan yo’llarni\n"
        "izlash – axir buning nimasi beandishalik? O’zingni bu oliyjanob ishlarga bag’ishlash –\n"
        "mas’uliyatni to’la his etish-ku! Axir biz hozirgacha nimani tushunib yetdik – baliqning\n"
        "ichak-chavog’ini talashib minglab yillarni boy berdik… Endi bizda ibtidomizni – nima\n"
        "12\n"
        "uchun yashayotganimizni anglash imkoniyati paydo bo’ldi. Kashf etish, tushunish,\n"
        "ozod bo’lish imkoniyati!..”",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1, 4"},
            {"is_correct": True, "letter": "B", "text": "2, 3"},
            {"is_correct": False, "letter": "C", "text": "1, 5"},
            {"is_correct": False, "letter": "D", "text": "2, 4"},
        ],
        "explanation": "Ushbu parcha Nabijon Boqiyning 'Mirkomilboyning qazo bo'lgan namozi' asaridan olingan (2) va "
        "takya so'zi ziyoratchilar uchun boshpana, maskan ma'nosini anglatadi (3).",
        "position": 33,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Quyidaparchasikeltirilgan asar haqidagi to’g’ri hukmni aniqlang.\n"
        "“ … Quv yoxud makkor bo’lganida, rahmatli otasining Makka va Madinada takya\n"
        "qurdirish niyatida niyatida o’ttiz ming tillo vasiyat qilib qoldirganini uyezd hokimiga\n"
        "aytarmidi?! Soyasidan cho’chisa, hatto o’z pushtikamaridan bo’lgan o’g’il-qizlaridan\n"
        "hadik-xavotirda yashasa, yeti yot begona, buning ustiga , g’ayridin Iskandarni\n"
        "gumashta qilib olarmidi?!.. ”\n"
        "1.Bu parcha “Muzqaymoq” hikoyasidan olingan\n"
        "2.Bu parcha “Mirkomilboyning qazo bo’lgan namozi” hikoyasidan olingan\n"
        "3.Badiiy parchada ajratib ko’rsatilgan so’z ma’nosi: takya so’zining ma’nosi –\n"
        "boshpana, turarjoy\n"
        "4.Badiiy parchada ajratib ko’rsatilgan so’z ma’nosi: takya so’zining ma’nosi – toza\n"
        "ichimli suvi saqlanadigan hovuz\n"
        "5.Ushbu hikoyada qamoqqa olingan otani izlab yo’lga chiqqan o’g’il voqeasi bayon\n"
        "qilingan",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Tazod, ishtiqoq san’atlari qo’llangan",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Nido, takrir san’atlari qo’llangan",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "Tajnis, iyhom san’atlari qo’llangan",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Tamsil, istiora san’atlari qo’llangan",
            },
        ],
        "explanation": "Baytda 'pok' so'zi birinchi misrada sifat (pokiza, toza), ikkinchi misrada ravish (butunlay, "
        "batamom) ma'nosida qo'llanib tajnis va iyhom san'atlarini hosil qilgan.",
        "position": 34,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Ushbubayt haqidagi to’g’ri javobni aniqlang.\n"
        "Aylar erduk pok ishq o’tig’a kuymak orzu,\n"
        "Shukrilillah, oqibat kuydurdi ishqing bizni pok.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Ul husnda tengi yo’q sanam gulshanga qadam qo’yganidan u yerdagi gullar uning\n"
                "zeboligini ko’rib yig’lashga tushadilar",
            },
            {
                "is_correct": True,
                "letter": "B",
                "text": "Mening sohinjamol yorim mingan o’sha ot hayotim gulshanini shod etuvchi\n"
                "ko’klamimning bulutidir",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Ul qalamqosh yorim gulshan ichra barcha gullarning ra’nosidur, lekin uning hajri\n"
                "tufayli ko’nglimdagi bulutlar tarqamayapti",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Husn bahori maydonga kirarmikin deb termuldim, siz ko’rayotgan bu ko’zimning\n"
                "qorasi emas, balki intizorlikning dog’idir",
            },
        ],
        "explanation": "Navoiy baytida 'bodpoy' — shamoldek chopqir ot, 'abri bahor' — bahor buluti. Nasriy mazmuni: "
        "Mening go'zal yorim mingan chopqir ot hayotim gulshanini quvontiruvchi ko'klam bulutidir.",
        "position": 35,
        "reading_passage_order": None,
        "section_code": "MUTAXASSISLIK",
        "text": "Navoiyqalamigamansubushbubaytningnasriybayoni to’g’ri berilgan\n"
        "javobni aniqlang.\n"
        "Ul bahori husn mingan qatraafshon bodpoy\n"
        "Gulshani aysh ochqali abri bahorimdur mening.",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Mazmunli ta’lim muhitini tashkil qilish va o‘zgartirish",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "O‘quvchilarda fuqarolik kompetensiyalari va media savodxonligini shakllantirish",
            },
            {
                "is_correct": True,
                "letter": "C",
                "text": "Turli madaniyatdagi bolalar va o‘spirinlar bilan ishlashga\n"
                "imkon beradigan madaniyatlararo kompetensiyalarga ega bo‘lish",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "O‘quvchilarga mas’uliyatli qaror qabul qilishga yordam berish",
            },
        ],
        "explanation": "Turli millat va madaniyatga mansub o'quvchilar o'rtasida bag'rikenglik va xavfsiz muhit "
        "yaratish pedagog kasb standartidagi 'madaniyatlararo kompetensiya' talabidir.",
        "position": 36,
        "reading_passage_order": None,
        "section_code": "KASB_STANDARTI",
        "text": "Sinfda turli hudud va millatlardan bo‘lgan o‘quvchilar\n"
        "birgalikda o‘qirdi. Ba’zi o‘quvchilar bir-birining urf-odatlarini tushunmasdan,\n"
        "kelishmovchilikka bordi. O‘qituvchi vaziyatni to‘xtatib, hurmat va bag‘rikenglik\n"
        "mavzusida suhbat o‘tkazdi. Turli madaniyatlarning ijobiy jihatlarini muhokama qildi.\n"
        "Sinfda o‘zaro tushunish va xavfsiz muhit mustahkamlandi.\n"
        "O‘qituvchi qaysi zarur ko‘nikmaga ega ekanligini ko‘rsatdi?",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Insoniyatni rivojlantirish, o‘qitish va tarbiyalashning klassik va zamonaviy "
                "nazariyalarini",
            },
            {
                "is_correct": True,
                "letter": "B",
                "text": "Bola huquqlari to‘g‘risidagi xalqaro konvensiyaning nizomlarini",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Ta’lim muassasalarida mehnat gigiyena qoidalari va texnika xavfsizligi "
                "qoidalarini",
            },
            {
                "is_correct": False,
                "letter": "D",
                "text": "Hayot xavfsizligi asoslarini",
            },
        ],
        "explanation": "Har bir bolaning erkin fikr bildirish huquqi borligi va kamsitilmasligini ta'minlash BMTning "
        "'Bola huquqlari to'g'risidagi xalqaro konvensiyasi' nizomlariga asoslanadi.",
        "position": 37,
        "reading_passage_order": None,
        "section_code": "KASB_STANDARTI",
        "text": "Dars davomida bir o‘quvchi noto‘g‘ri javob berdi. Sinfdoshlarining ayrimlari kulib\n"
        "yubordi. O‘qituvchi vaziyatni to‘xtatib, har bir bolaning fikr bildirish huquqi borligini\n"
        "aytdi. Hech kim kamsitilmasligi kerakligini tushuntirdi. Shundan so‘ng dars tinch va\n"
        "xavfsiz muhitda davom etdi.O‘qituvchi qaysizarur bilimgaega ekanligini\n"
        "namoyon etdi?",
    },
    {
        "choices": [
            {
                "is_correct": False,
                "letter": "A",
                "text": "Oʻzingizning kasbiy oʻsishi, shu jumladan, oʻz-oʻzini rivojlanish yoʻlini "
                "aniqlash",
            },
            {
                "is_correct": False,
                "letter": "B",
                "text": "Kasbiy rivojlanishida AKT muhitidan foydalanish",
            },
            {
                "is_correct": False,
                "letter": "C",
                "text": "Oʻzining taʼlim faoliyatini tahlil qilish va baholash, modifikatsiyani talab "
                "qiladigan\n"
                "yoʻnalishlarni aniqlash",
            },
            {
                "is_correct": True,
                "letter": "D",
                "text": "Faoliyatida chet tilidan foydalanish (zaruriyat boʻlganda)",
            },
        ],
        "explanation": "O'qituvchining chet tilidagi ilmiy manbalarni o'rganib darsga tatbiq etishi kasbiy "
        "standartdagi 'Faoliyatida chet tilidan foydalanish (zaruriyat bo'lganda)' ko'nikmasidir.",
        "position": 38,
        "reading_passage_order": None,
        "section_code": "KASB_STANDARTI",
        "text": "O‘qituvchi yangi pedagogik metodlar bo‘yicha mahalliy manbalar yetarli\n"
        "emasligini sezdi. Shu sababli chet tilidagi metodik qo‘llanmalar va maqolalarni\n"
        "o‘rganishga murojaat qildi. Kerakli ma’lumotlarni tarjima qilib, darslariga\n"
        "moslashtirdi. Yangi yondashuvlarni amaliyotda sinab ko‘rdi. Dars sifati sezilarli\n"
        "darajada oshdi.O‘qituvchida qaysi zaruriy ko‘nikma bor?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "Maqsadni belgilash bosqichi"},
            {"is_correct": False, "letter": "B", "text": "Metod tanlash bosqichi"},
            {
                "is_correct": True,
                "letter": "C",
                "text": "Mavzuga doir materiallarni yig‘ish va saralash bosqichi",
            },
            {"is_correct": False, "letter": "D", "text": "Nazorat bosqichi"},
        ],
        "explanation": "Mavzu bo'yicha turli darsliklarni o'rganish, saralash va asosiy qismlarni ajratib olish — "
        "darsni loyihalashning 'Mavzuga doir materiallarni yig'ish va saralash bosqichi' hisoblanadi.",
        "position": 39,
        "reading_passage_order": None,
        "section_code": "KASB_STANDARTI",
        "text": "O‘qituvchi yangi mavzuni o‘tishdan oldin turli darsliklar va qo‘llanmalarni\n"
        "o‘rgandi. U mavzuga oid barcha kerakli ma’lumotlarni yig‘ib chiqdi. So‘ng ularni\n"
        "saralab, asosiy va qo‘shimcha qismlarga ajratdi. Keraksiz yoki ortiqcha ma’lumotlarni\n"
        "14\n"
        "chiqarib tashladi. Dars mazmunini aniq va tushunarli shaklga keltirdi. Ushbu holat\n"
        "loyihalashning qaysi bosqichiga kiradi?",
    },
    {
        "choices": [
            {"is_correct": True, "letter": "A", "text": "bayon qilish metodi"},
            {"is_correct": False, "letter": "B", "text": "suhbat metodi"},
            {"is_correct": False, "letter": "C", "text": "reproduktiv metod"},
            {"is_correct": False, "letter": "D", "text": "ma'ruza metodi"},
        ],
        "explanation": "O'qituvchining dars mavzusi va qoidalarini aniq, lo'nda va misollar tahlili bilan izchil "
        "tushuntirib berishi — bayon qilish (tushuntirish) metodidir.",
        "position": 40,
        "reading_passage_order": None,
        "section_code": "KASB_STANDARTI",
        "text": "Insonlarning kasb-hunarini bildirgan so‘zlar ham Kim?\n"
        "so‘rog‘iga javob bo‘ladi. Kim? – haydovchi, dehqon, bog‘bon. Narsalarning nomini\n"
        "bildirgan so‘zlar Nima? so‘rog‘iga javob bo‘ladi. Nima? – ayiq, tosh, daftar.\n"
        "O`qituvchi dars davomida bolalarga ushbu qoidani o`rgatishdan avval oldin\n"
        "o‘quvchilarning o‘rganilayotgan mavzu yuzasidan bilimlarini aniqlab oldi. Bunda\n"
        "o‘qituvchi o‘rganilayotgan grammatik mavzuning muhim o‘rinlarini aniq, lo‘nda,\n"
        "misollar tahlili bilan izchil aytib berdi.Qaysi metoddan foydalanilmoqda?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1–a, 2–b, 3–c, 4–d"},
            {"is_correct": False, "letter": "B", "text": "1–b, 2–c, 3–d, 4–a"},
            {"is_correct": False, "letter": "C", "text": "1–d, 2–a, 3–b, 4–c"},
            {"is_correct": True, "letter": "D", "text": "1–c, 2–a, 3–b, 4–d"},
        ],
        "explanation": "Tamoyillar mosligi: 1-Ko'p omillilik (c: kompleks omillarni hisobga olish); 2-Shaxsga "
        "yo'naltirilganlik (a: individual xususiyatlarga mos yondashuv); 3-Tabiiy rivojlanish va "
        "ijtimoiylashuv (b: yosh va jamiyatga moslashuv); 4-Ijtimoiy-iqtisodiy ta'minot (d: "
        "moddiy-texnik baza). Javob: 1–c, 2–a, 3–b, 4–d (D).",
        "position": 41,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "Moslashtiring:\n"
        "1. Ko‘p omillilik tamoyili\n"
        "2. Shaxsga yo‘naltirilganlik tamoyili\n"
        "3. Tabiiy rivojlanish va ijtimoiylashuv tamoyili\n"
        "4. Ijtimoiy-iqtisodiy ta’minot tamoyili\n"
        "a) Ta’lim jarayonida har bir o‘quvchining individual xususiyatlari, qobiliyatlari,\n"
        "qiziqishlari va ehtiyojlarini hisobga olib, unga mos yondashuvni tashkil etish\n"
        "b) Ta’lim jarayonida o‘quvchining yosh xususiyatlari, tabiiy rivojlanish bosqichlari\n"
        "hamda jamiyatga moslashuv jarayonini inobatga olib faoliyatni tashkil etish\n"
        "c) Ta’lim jarayonining samaradorligiga ta’sir etuvchi turli pedagogik, psixologik,\n"
        "ijtimoiy va tashkiliy omillarni kompleks tarzda hisobga olish\n"
        "d) Ta’lim jarayonini samarali tashkil etish uchun zarur bo‘lgan moddiy-texnik baza,\n"
        "sharoitlar, boshqaruv va ijtimoiy muhitni hisobga olish",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "1–a, 2–b, 3–c, 4–d"},
            {"is_correct": False, "letter": "B", "text": "1–b, 2–c, 3–d, 4–a"},
            {"is_correct": False, "letter": "C", "text": "1–c, 2–d, 3–a, 4–b"},
            {"is_correct": True, "letter": "D", "text": "1–d, 2–c, 3–a, 4–b"},
        ],
        "explanation": "Tamoyillar mosligi: 1-Markazlashtirish (d: o'quvchi faoliyatini markazga qo'yish); "
        "2-Natijaviylik (c: belgilangan bilim va malakalarga erishish); 3-Refleksivlik (a: o'z "
        "faoliyatini va xatolarini tahlil qilish); 4-Axborot ta'minoti (b: o'quv va metodik manbalar "
        "bilan to'liq ta'minlash). Javob: 1–d, 2–c, 3–a, 4–b (D).",
        "position": 42,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "Moslashtiring:\n"
        "1. Markazlashtirish tamoyili\n"
        "2. Natijaviylik tamoyili\n"
        "3. Refleksivlik tamoyili\n"
        "4. Axborot ta’minoti tamoyili\n"
        "a) Ta’lim jarayonida o‘quvchilarning o‘z faoliyatini tahlil\n"
        "15\n"
        "qilishi, o‘z xatolarini aniqlashi va kelgusi faoliyatini\n"
        "yaxshilashga qaratilgan jarayonni tashkil etish\n"
        "b) Ta’lim jarayonini zarur o‘quv materiallari, metodik qo‘llanmalar, texnik vositalar\n"
        "va axborot manbalari bilan to‘liq ta’minlash\n"
        "c) Ta’lim jarayonini aniq maqsad asosida tashkil etib, yakunda o‘quvchilarda\n"
        "belgilangan bilim, ko‘nikma va malakalarni shakllantirishga erishish\n"
        "d) Ta’lim jarayonida o‘quvchi faoliyatini asosiy o‘ringa qo‘yish, uning mustaqil\n"
        "fikrlashi, faol ishtiroki va bilimni o‘zlashtirish jarayonini markazga chiqarish",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "Refleksivlik"},
            {"is_correct": False, "letter": "B", "text": "Markazlashtirish"},
            {"is_correct": True, "letter": "C", "text": "Natijaviylik"},
            {"is_correct": False, "letter": "D", "text": "Vosita"},
        ],
        "explanation": "Dars avvalida aniq o'lchanadigan maqsad qo'yib, dars yakunida aynan shu maqsadga erishilganlik "
        "darajasini baholash — natijaviylik tamoyilidir.",
        "position": 43,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "O‘qituvchi darsni boshlashdan oldin aniq maqsad qo‘ydi: o‘quvchilar mavzuni\n"
        "tushunib, misollarni mustaqil yecha olishi kerak edi. Dars davomida barcha\n"
        "topshiriqlar aynan shu maqsadga xizmat qildi. Dars oxirida o‘quvchilarga test berilib,\n"
        "ularning bilim darajasi tekshirildi. Ko‘pchilik o‘quvchilar to‘g‘ri javob berdi. Natijada\n"
        "dars samaradorligi aniq baholandi.Bu qaysi tamoyil?",
    },
    {
        "choices": [
            {"is_correct": True, "letter": "A", "text": "Refleksivlik"},
            {"is_correct": False, "letter": "B", "text": "Natijaviylik"},
            {"is_correct": False, "letter": "C", "text": "Ko‘p omillilik"},
            {"is_correct": False, "letter": "D", "text": "Nazorat"},
        ],
        "explanation": "O'quvchilar va o'qituvchining o'z-o'zini baholashi, qiyinchilik va yutuqlarni tahlil qilib "
        "xulosalar chiqarishi — refleksivlik tamoyilidir.",
        "position": 44,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "Dars yakunida o‘qituvchi o‘quvchilarga bugungi mavzu bo‘yicha o‘z fikrlarini\n"
        "yozib berishni topshirdi. O‘quvchilar qaysi joyni yaxshi tushunganini va qaysi qism\n"
        "qiyin bo‘lganini yozdi. O‘qituvchi ham o‘z darsini tahlil qilib, qaysi metod samarali\n"
        "bo‘lganini aniqladi. Keyingi darsda kamchiliklarni tuzatishga qaror qildi. Jarayonda\n"
        "o‘z-o‘zini baholash muhim rol o‘ynadi. Bu qaysi tamoyil?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "Natijaviylik"},
            {"is_correct": True, "letter": "B", "text": "Markazlashtirish"},
            {"is_correct": False, "letter": "C", "text": "Refleksivlik"},
            {"is_correct": False, "letter": "D", "text": "Axborot"},
        ],
        "explanation": "O'qituvchi faqat yo'naltiruvchi (fasilitator) bo'lib, butun dars faoliyati o'quvchilarning "
        "mustaqil izlanishi va muhokamasiga asoslanishi — markazlashtirish (o'quvchiga "
        "yo'naltirilganlik) tamoyiliga mos keladi.",
        "position": 45,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "Dars jarayonida o‘qituvchi mavzuni qisqacha tushuntirdi va darhol o‘quvchilarni\n"
        "kichik guruhlarga ajratdi. Har bir guruhga muammo berilib, ular mustaqil ravishda\n"
        "yechim topishga harakat qildi. O‘quvchilar o‘z fikrlarini bahs-munozara orqali asoslab\n"
        "berdi. O‘qituvchi faqat yo‘naltiruvchi rolni bajardi. Dars davomida asosiy faoliyat\n"
        "o‘quvchilar tomonidan amalga oshirildi.Bu qaysi tamoyilgamos?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "Umumiy vazifa"},
            {"is_correct": False, "letter": "B", "text": "Bosqichli vazifa"},
            {"is_correct": True, "letter": "C", "text": "Vaziyatli vazifa"},
            {"is_correct": False, "letter": "D", "text": "Baholash"},
        ],
        "explanation": "Kutilmagan vaziyatlarda dars rejasini tezkor moslashtirish, tushunarsiz joyda boshqa metodga "
        "o'tish qobiliyati — vaziyatli vazifani talab qiladi.",
        "position": 46,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "O‘qituvchi darsni mukammal rejaladi: kirish, asosiy qism va yakun bor edi. Lekin\n"
        "dars davomida o‘quvchilar mavzuni tushunmay qoldi va o‘qituvchi metodni\n"
        "o‘zgartirmadi. Shu sababli dars samarasi past bo‘ldi. Bu holatda qaysi vazifa turi\n"
        "yetishmadi?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "Tezkor tashxis"},
            {"is_correct": True, "letter": "B", "text": "Davomli tashxis"},
            {"is_correct": False, "letter": "C", "text": "Bir martalik nazorat"},
            {"is_correct": False, "letter": "D", "text": "Test"},
        ],
        "explanation": "O'quvchini bir oy davomida muntazam kuzatib, natijalarini haftama-hafta solishtirish va "
        "individual reja tuzish — davomli (longityud) tashxis turidir.",
        "position": 47,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "O‘qituvchi o‘quvchini bir oy davomida kuzatdi. U o‘quvchining bilim darajasi,\n"
        "qiziqishi va xulq-atvorini tahlil qildi. Har hafta natijalarni solishtirib bordi. Yakunda\n"
        "o‘quvchi uchun individual reja tuzdi. Bu qaysi tashxis turiga kiradi?",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "Tadqiqot"},
            {"is_correct": True, "letter": "B", "text": "Qisman izlanish"},
            {"is_correct": False, "letter": "C", "text": "Muammoli bayon"},
            {"is_correct": False, "letter": "D", "text": "Reproduktiv"},
        ],
        "explanation": "O'qituvchi muammoli savollar berib, o'quvchilarni mustaqil fikrlashga yo'naltirib turishi — "
        "qisman izlanish (evristik) metodidir.",
        "position": 48,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "O‘qituvchi dars davomida o‘quvchilarga savollar berib, ularni muammoni\n"
        "yechishga jalb qildi: “Qaysi sabab asosiy deb o‘ylaysiz?” “Buni qanday isbotlaysiz?”\n"
        "O‘quvchilar o‘z fikrlarini bildirdi, lekin o‘qituvchi yo‘naltirib turdi.",
    },
    {
        "choices": [
            {"is_correct": False, "letter": "A", "text": "Muammoli bayon"},
            {
                "is_correct": True,
                "letter": "B",
                "text": "Muammoli boshlash bilan bayon",
            },
            {"is_correct": False, "letter": "C", "text": "Tadqiqot"},
            {"is_correct": False, "letter": "D", "text": "Qisman izlanish"},
        ],
        "explanation": "Dars boshida qiziqarli muammoli vaziyat yaratib, so'ngra mavzuni tushuntirish orqali bayon "
        "qilish — 'Muammoli boshlash bilan bayon' metodi deb ataladi.",
        "position": 49,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "O‘qituvchi dars boshida qiziqarli va tushunarsiz vaziyat yaratdi. O‘quvchilar savol\n"
        "bilan qiziqdi, lekin o‘qituvchi keyin mavzuni oddiy tushuntirish orqali bayon qildi.",
    },
    {
        "choices": [
            {"is_correct": True, "letter": "A", "text": "Ta’lim maqsadi"},
            {"is_correct": False, "letter": "B", "text": "Ta’lim mazmuni"},
            {"is_correct": False, "letter": "C", "text": "Metod"},
            {"is_correct": False, "letter": "D", "text": "Natija"},
        ],
        "explanation": "Dars boshlanishidan avval kutilayotgan yakuniy natijalar va erishilishi lozim bo'lgan "
        "marralarni aniq belgilab olish — ta'lim maqsadi tarkibiy qismidir.",
        "position": 50,
        "reading_passage_order": None,
        "section_code": "PEDAGOGIKA",
        "text": "O‘qituvchi darsni boshlashdan oldin o‘quvchilarga nimaga erishish kerakligini\n"
        "aniq belgiladi. U dars oxirida o‘quvchilar qanday bilim va ko‘nikmaga ega bo‘lishini\n"
        "yozib chiqdi. Shu maqsad asosida dars mazmuni va metodlari tanlandi. Barcha faoliyat\n"
        "aynan shu yo‘nalishga qaratildi. Natijada dars aniq yo‘nalishda olib borildi.\n"
        "Bu qaysi tarkibiy qismga kiradi?",
    },
]


class Command(BaseCommand):
    help = (
        "Seeds 50-talik Rasmiy Attestatsiya Diagnostika 2026 testini bazaga kiritish."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Eski attestatsiya testini o'chirib qaytadan yaratish.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        reset: bool = options.get("reset", False)
        self.stdout.write(
            self.style.NOTICE(
                "Attestatsiya Diagnostika 2026 testini seed qilish boshlandi..."
            )
        )

        # 1. Instructor
        instructor = User.objects.filter(role="teacher").first()
        if not instructor:
            instructor = User.objects.filter(is_superuser=True).first()
        if not instructor:
            instructor = User.objects.filter(is_staff=True).first()
        if not instructor:
            instructor = User.objects.create(
                email="teacher@grandec.uz",
                first_name="Grand",
                last_name="Education",
                role="teacher",
                is_active=True,
                is_staff=True,
            )
            instructor.set_password("GrandEducation2026!")
            instructor.save()
            self.stdout.write(
                self.style.SUCCESS(f"O'qituvchi yaratildi: {instructor.email}")
            )

        # 2. Category: Attestatsiya
        category, _ = Category.objects.get_or_create(
            slug="attestatsiya",
            defaults={
                "name": "Attestatsiya",
                "description": "O'qituvchilarning malaka toifasi (attestatsiya) imtihonlari uchun diagnostik testlar.",
            },
        )
        if category.name != "Attestatsiya":
            category.name = "Attestatsiya"
            category.save(update_fields=["name"])

        # 3. Course
        course, _ = Course.objects.get_or_create(
            slug="ona-tili-va-adabiyot-attestatsiya-2026",
            defaults={
                "title": "Ona tili va Adabiyot (Attestatsiya 2026)",
                "description": (
                    "O'qituvchilarning malaka toifasi (attestatsiya) imtihonlari uchun yangi formatdagi "
                    "50 talik namunaviy diagnostika kursi."
                ),
                "teacher": instructor,
                "category": category,
                "status": Course.Status.PUBLISHED,
                "price": Decimal("0.00"),
            },
        )
        if (
            course.category_id != category.id
            or course.status != Course.Status.PUBLISHED
        ):
            course.category = category
            course.status = Course.Status.PUBLISHED
            course.price = Decimal("0.00")
            course.save(update_fields=["category", "status", "price"])

        # 4. Scoring Profile
        profile, _ = ExamScoringProfile.objects.get_or_create(
            name="attestatsiya-2026",
            version="v1",
            defaults={
                "is_active": True,
                "is_verified": True,
                "weights": {
                    "MUTAXASSISLIK": 1,
                    "KASB_STANDARTI": 1,
                    "PEDAGOGIKA": 1,
                },
            },
        )
        if not profile.is_verified:
            profile.is_verified = True
            profile.save(update_fields=["is_verified"])

        # 5. Test
        mock_code = "#MOCK-ATTEST2026"
        test = Test.objects.filter(mock_code=mock_code).first()
        if not test:
            test = Test.objects.filter(mock_code="MOCK-ATTEST2026").first()
        if not test:
            test = Test.objects.filter(
                title="Ona tili va Adabiyot — Rasmiy Attestatsiya Diagnostika 2026"
            ).first()

        if test and reset:
            self.stdout.write(
                self.style.WARNING("Eski test o'chirilmoqda (--reset)...")
            )
            test.delete()
            test = None

        test_title = "Ona tili va Adabiyot — Rasmiy Attestatsiya Diagnostika 2026"
        test_desc = (
            "O'qituvchilarning malaka toifasi (attestatsiya) imtihonlari uchun yangi formatdagi "
            "50 talik namunaviy diagnostika testi. Mutaxassislik, kasb standarti va pedagogik mahorat "
            "savollarini o'z ichiga oladi."
        )

        if not test:
            test = Test.objects.create(
                title=test_title,
                description=test_desc,
                course=course,
                time_limit_minutes=100,
                difficulty=Test.Difficulty.HARD,
                status=Test.Status.PUBLISHED,
                pass_percentage=60,
                max_attempts=0,
                mock_code=mock_code,
                show_results_immediately=True,
                shuffle_questions=False,
                shuffle_choices=False,
                scoring_profile=profile,
            )
            self.stdout.write(
                self.style.SUCCESS(f"Yangi test yaratildi: {test.title} (id={test.id})")
            )
        else:
            test.title = test_title
            test.description = test_desc
            test.course = course
            test.time_limit_minutes = 100
            test.difficulty = Test.Difficulty.HARD
            test.status = Test.Status.PUBLISHED
            test.pass_percentage = 60
            test.max_attempts = 0
            test.mock_code = mock_code
            test.show_results_immediately = True
            test.shuffle_questions = False
            test.shuffle_choices = False
            test.scoring_profile = profile
            test.save()
            self.stdout.write(
                self.style.NOTICE(
                    f"Mavjud test yangilandi: {test.title} (id={test.id})"
                )
            )

        # 6. Sections
        sec1, _ = ExamSection.objects.update_or_create(
            test=test,
            code="MUTAXASSISLIK",
            defaults={
                "name": "Mutaxassislik fani (Ona tili va adabiyot)",
                "order": 1,
                "duration_minutes": 0,
                "weight": Decimal("1.00"),
            },
        )
        sec2, _ = ExamSection.objects.update_or_create(
            test=test,
            code="KASB_STANDARTI",
            defaults={
                "name": "Kasbiy standart (O'qituvchi kompetensiyalari)",
                "order": 2,
                "duration_minutes": 0,
                "weight": Decimal("1.00"),
            },
        )
        sec3, _ = ExamSection.objects.update_or_create(
            test=test,
            code="PEDAGOGIKA",
            defaults={
                "name": "Pedagogik mahorat va metodika",
                "order": 3,
                "duration_minutes": 0,
                "weight": Decimal("1.00"),
            },
        )
        section_map = {
            "MUTAXASSISLIK": sec1,
            "KASB_STANDARTI": sec2,
            "PEDAGOGIKA": sec3,
        }

        # 7. Passages
        p1, _ = ReadingPassage.objects.update_or_create(
            test=test,
            order=1,
            defaults={
                "section": sec1,
                "title": PASSAGE_1_TITLE,
                "content": PASSAGE_1_CONTENT,
                "source": "M. Bobojonov",
            },
        )
        p2, _ = ReadingPassage.objects.update_or_create(
            test=test,
            order=2,
            defaults={
                "section": sec1,
                "title": PASSAGE_2_TITLE,
                "content": PASSAGE_2_CONTENT,
                "source": "Badiiy satirik hikoya",
            },
        )
        passage_map = {1: p1, 2: p2}

        # 8. Questions and Choices
        existing_questions = {q.position: q for q in test.questions.all()}
        created_q = 0
        updated_q = 0

        for q_item in QUESTIONS_DATA:
            pos = q_item["position"]
            sec = section_map[q_item["section_code"]]
            pass_obj = passage_map.get(q_item["reading_passage_order"])

            q_obj = existing_questions.get(pos)
            if not q_obj:
                q_obj = Question.objects.create(
                    test=test,
                    section=sec,
                    reading_passage=pass_obj,
                    text=q_item["text"],
                    question_type=Question.QuestionType.SINGLE_CHOICE,
                    points=1,
                    position=pos,
                    explanation=q_item["explanation"],
                )
                created_q += 1
            else:
                q_obj.section = sec
                q_obj.reading_passage = pass_obj
                q_obj.text = q_item["text"]
                q_obj.question_type = Question.QuestionType.SINGLE_CHOICE
                q_obj.points = 1
                q_obj.explanation = q_item["explanation"]
                q_obj.save()
                updated_q += 1

            # Choices
            q_obj.choices.all().delete()
            choices_to_create = []
            for ci, c_data in enumerate(q_item["choices"], start=1):
                choices_to_create.append(
                    Choice(
                        question=q_obj,
                        text=f"{c_data['letter']}) {c_data['text']}",
                        position=ci,
                        is_correct=c_data["is_correct"],
                    )
                )
            Choice.objects.bulk_create(choices_to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"Muvaffaqiyatli yakunlandi: {created_q} yangi savol, {updated_q} yangilangan savol. Jami 50 ta savol!"
            )
        )
