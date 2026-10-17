"""
Django Management Command: seed_bmb_mock_day4

Seeds the full 3-hour official BMB State Standard Exam (Day 4):
- 44 Test Questions (Grammar, Scientific Reading "Bakteriyalar", Literary Reading "Hushtak", Classical Ghazal Navoiy, Syntactic Matching, Short Written)
- Task 45: Official 12-criteria Essay with EssayTopic synchronization
- Full AI Repetitor educational explanations for every single question.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import Category, Course
from apps.essays.models import EssayTopic
from apps.tests.models import (
    Choice,
    ExamSection,
    Question,
    ReadingPassage,
    Test,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds BMB Milliy Sertifikat Mock #4 (Day 4) into the platform."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing Mock #4 test before recreating.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        reset: bool = options.get("reset", False)
        self.stdout.write(self.style.NOTICE("Seeding BMB Milliy Sertifikat Mock #4 (3-hour format)..."))

        # 1. Instructor User
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
            self.stdout.write(self.style.SUCCESS(f"Created instructor account: {instructor.email}"))

        # 2. Category
        category, _ = Category.objects.get_or_create(
            slug="milliy-sertifikat",
            defaults={
                "name": "Milliy Sertifikat",
                "description": "Ona tili va adabiyot fanidan BMB davlat milliy sertifikatiga tayyorgarlik kursi va diagnostikalari.",
            },
        )

        # 3. Course
        course, _ = Course.objects.get_or_create(
            slug="ona-tili-va-adabiyot-milliy-sertifikat",
            defaults={
                "title": "Ona tili va Adabiyot (Milliy Sertifikat)",
                "description": "BMB rasmiy davlat standarti asosidagi to'liq 3 soatlik milliy sertifikat diagnostika imtihonlari va AI esse tahlili.",
                "teacher": instructor,
                "category": category,
                "status": Course.Status.PUBLISHED,
                "price": Decimal("0.00"),
            },
        )
        if course.status != Course.Status.PUBLISHED or course.price != Decimal("0.00"):
            course.status = Course.Status.PUBLISHED
            course.price = Decimal("0.00")
            course.save(update_fields=["status", "price"])

        # 4. Test
        mock_code = "#MOCK-BMB04"
        existing_test = Test.objects.filter(mock_code=mock_code).first()
        if existing_test and reset:
            self.stdout.write(self.style.WARNING("Reset requested: Deleting existing Mock #4 test..."))
            existing_test.delete()
            existing_test = None

        if existing_test:
            test = existing_test
            test.title = "Ona tili va Adabiyot — BMB Milliy Sertifikat Mock #4 (To'liq format)"
            test.description = (
                "Haqiqiy 3 soatlik BMB davlat standarti imtihoni. 44 ta test savoli "
                "(grammatika, ilmiy va badiiy matnlar, mumtoz adabiyot, sintaktik tahlil) "
                "hamda 12 mezonli rasmiy Esse."
            )
            test.time_limit_minutes = 180
            test.difficulty = Test.Difficulty.HARD
            test.status = Test.Status.PUBLISHED
            test.pass_percentage = 60
            test.max_attempts = 0
            test.show_results_immediately = True
            test.shuffle_questions = False
            test.shuffle_choices = False
            test.save()
            # Clear old child relations to re-populate cleanly
            test.questions.all().delete()
            test.passages.all().delete()
            test.sections.all().delete()
            self.stdout.write(self.style.NOTICE(f"Updated existing test ID: {test.id}"))
        else:
            test = Test.objects.create(
                title="Ona tili va Adabiyot — BMB Milliy Sertifikat Mock #4 (To'liq format)",
                description=(
                    "Haqiqiy 3 soatlik BMB davlat standarti imtihoni. 44 ta test savoli "
                    "(grammatika, ilmiy va badiiy matnlar, mumtoz adabiyot, sintaktik tahlil) "
                    "hamda 12 mezonli rasmiy Esse."
                ),
                course=course,
                time_limit_minutes=180,
                difficulty=Test.Difficulty.HARD,
                status=Test.Status.PUBLISHED,
                pass_percentage=60,
                max_attempts=0,
                mock_code=mock_code,
                show_results_immediately=True,
                shuffle_questions=False,
                shuffle_choices=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Created new test ID: {test.id} with code {mock_code}"))

        # 5. Exam Sections
        sec_lang, _ = ExamSection.objects.get_or_create(
            test=test,
            code=ExamSection.LANGUAGE,
            defaults={"name": "Grammatika va adabiyot", "order": 1, "weight": Decimal("1.00")},
        )
        sec_reading, _ = ExamSection.objects.get_or_create(
            test=test,
            code=ExamSection.READING,
            defaults={"name": "Ilmiy va badiiy matnlar tahlili", "order": 2, "weight": Decimal("1.00")},
        )
        sec_lit, _ = ExamSection.objects.get_or_create(
            test=test,
            code=ExamSection.LITERATURE,
            defaults={"name": "Mumtoz adabiyot va poetika", "order": 3, "weight": Decimal("1.00")},
        )
        sec_writing, _ = ExamSection.objects.get_or_create(
            test=test,
            code=ExamSection.WRITING,
            defaults={"name": "BMB Rasmiy Esse", "order": 4, "weight": Decimal("1.00")},
        )

        # 6. Reading Passages
        p1_content = (
            "BAKTERIYALAR\n\n"
            "I QISM:\n"
            "Bakteriyalar bir hujayrali mikroorganizmlarning katta guruhi. Bakteriya koʻndalangiga boʻlinish "
            "yoʻli bilan koʻpayadi. Bakteriyaning koʻp turi tayoqcha shaklida boʻladi. Biroq sharsimon, ipsimon "
            "yoki buralgan shaklli mikroorganizmlar ham bakteriyaga kiradi. Bakteriyalar yagona bir guruh boʻlmay, "
            "har xil yoʻllar bilan vujudga kelgan organizmlardir. Baʼzi bakteriyalar koʻk-yashil suvoʻtlarga yaqin, "
            "ayrim bakteriyalar esa nursimon zamburugʻlar — aktinomitsetlar bilan urugʻdosh; spiroxetalar va boshqa "
            "baʼzi bakteriyalar bir hujayrali sodda hayvonlarga oʻxshaydi.\n\n"
            "II QISM:\n"
            "Bakteriyaning katta-kichikligi, shakli, tuzilishi, harakatchanligi har xil. Sharsimon bakteriyalar kokklar "
            "deb ataladi. Agar kokklar koʻndalangiga boʻlinish yoʻli bilan koʻpaysa va boʻlingandan keyin bir-biriga "
            "qoʻshilganligicha qolib zanjir hosil qilsa, streptokokklar deyiladi. Hujayralar uchta oʻzaro tik yoʻnalishda "
            "boʻlinsa, hujayralar xaltachasi (paketi)ni hosil qiladi, bunday shakl sarsinalar uchun xos. Sporalar hosil "
            "qiladigan tayoqchasimon bakteriyalar batsillalar deyiladi. Tayoqchasimon bakteriyaning uchlari tekis "
            "'qirqilgan' yoki doʻngroq boʻlishi mumkin. Bular alohida yoki, baʼzan, zanjir shaklida joylashadi. "
            "Sitoplazmada ribosomalar boʻlib, ular tarkibiga RNK kiradi.\n\n"
            "III QISM:\n"
            "Bakteriya yuqori temperaturaga, odatda, chidamsiz, quritish, oftob, har xil kimyoviy moddalar bakteriyani "
            "oʻldiradi. Bakteriyalar sovuqqa juda chidamli, shu tufayli tuproqda qishlab chiqa oladi. Bakteriyaning "
            "koʻpi oval yoki aylana shaklli sporalar hosil qiladi. Bakteriya sporalari yuqori temperatura va zaharli "
            "moddalar taʼsiriga juda bardoshli. Sporalar qulay muhitga tushganda ulardan tayoqchasimon yoki vegetativ "
            "hujayralar paydo boʻladi. Bakteriyaning rivojlanish sikli har xil. Masalan, mikobakteriyalar boʻlinish "
            "yoʻli bilan ham, kurtaklanish yoʻli bilan ham koʻpayadi. Miksobakteriyalarning vegetativ hujayralari "
            "qisqaradi va kichrayib, yumaloq yoki oval shaklli mikrotsistalar hosil qiladi.\n\n"
            "IV QISM:\n"
            "Faqat kislorodli muhitda yashay oladigan bakteriyalar aeroblar, kislorodsiz muhitda yashaydigan bakteriyalar "
            "anaeroblar deyiladi. Aerob nafas olish vaqtida organik birikmalar oksidlanib, karbonat angidrid ajralib chiqadi. "
            "Anaerob sharoitda organik birikmalarning parchalanishi va bunda energiya ajralib chiqishi bijgʻish deyiladi. "
            "Hayvonlar oʻziga zarur azotli birikmalarni oʻsimlik oqsillaridan hosil qiladi. Hayvon va oʻsimlik oqsillari "
            "bakteriya taʼsirida minerallashib, avval ammiakka, keyin nitrit va nitratlarga aylanadi. Odam va hayvonlarda "
            "kasallik qoʻzgʻatadigan bakteriya patogen bakteriya deb ataladi. Fitopatogen bakteriya yovvoyi oʻsimliklarda "
            "ham, ekinlarda ham koʻpgina kasalliklarni vujudga keltiradi."
        )
        passage1 = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            title="Bakteriyalar (Ilmiy matn)",
            content=p1_content,
            order=1,
            source="Biologiya va mikrobiologiya asoslari",
        )

        p2_content = (
            "Benjamin Franklin. Hushtak (hikoya)\n\n"
            "Aziz do‘stim, chorshanba va shanba kuni yo‘llagan bir juft maktubingizni oldim. Bugun yana chorshanba. "
            "Avvalgisiga javob yozmaganim uchun maktub olishdan mahrum bo‘ldim. Biroq, garchi yalqov bo‘lsam-da va "
            "maktub bitishni xush ko‘rmasam-da, agar o‘zim javob yozmasam, boshqa hech qachon Sizning dilkash bitigingizni "
            "o‘qiy olmasligim yuzasidan cheksiz xavotir qo‘limga qalam tutishga majbur etdi. Shu bois janob B. ertaga Sizni "
            "yo‘qlab borish niyatida ekani to‘g‘risida iltifot ila ma’lum qilganida ham bu chorshanbani avvalgilari kabi "
            "Sizning dilkash davrangizda emas, Siz haqingizda o‘y surib o‘tkazishga: Sizga maktub bitish, nomalaringizni "
            "qayta-qayta o‘qib chiqishga ahd qildim.\n\n"
            "Sizning jannat va u yerdagi hayot to‘g‘risidagi ta’rifingiz meni maftun etdi. Jannatga bu olamdan imkon qadar "
            "hamma yaxshi narsalarni olib o‘tishimiz kerakligi to‘g‘risidagi xulosangizni bag‘oyat ma’qullayman. Fikrimcha, "
            "agar hushtaklar uchun haddan ortiq haq to‘lamaganimizda edi, hozirgidan ko‘ra ko‘proq narsalarga ega bo‘lishimiz, "
            "yovuzlikdan kamroq azob chekishimiz mumkin edi. Chunki biz duch keladigan baxtsiz odamlar, menimcha, ana shu "
            "ehtiyotsizlik tufayli saodatni boy berganlar.\n\n"
            "Nimani nazarda tutayapti, deb so‘rarsiz? Siz hikoyalarni yoqtirasiz. Shu bois o‘zim to‘g‘rimdagi bir hikoyani "
            "so‘zlab bermoqchiman. Va buning uchun meni ma’zur tutgaysiz. Yoshim yettida edi. Bayramlarning birida o‘rtoqlarim "
            "menga bir hovuch chaqa sovg‘a qilishdi. Men o‘sha zahoti o‘yinchoqlar do‘koniga ravona bo‘ldim. Yo‘lda "
            "ketayotganimda bir bolaning qo‘lidagi hushtakning sadosi hushimni o‘g‘irladi va do‘konga kirib bor pulimga "
            "hushtak sotib oldim. Keyin uyga qaytdim-da, sevinchim ichimga sig‘may quloqni qomatga keltirib hushtak chala boshladim.\n\n"
            "Bundan uydagilarning achchig‘i chiqsa-da, men juda sarmast edim. Akalarim, opalarim, amakivachchalarim hushtakning "
            "bahosini surishtirib bilgach, uni o‘z narxidan to‘rt baravar qimmatga sotib olganimni, qolgan pulga qanday "
            "yaxshi narsalar sotib olishim mumkinligini aytib, ustimdan rosa kulishdi. Xo‘rligim kelib yig‘lab yubordim. "
            "Hushtak tufayli chekkan bu iztirobim, u keltirgan quvonch va lazzatdan ziyodroq edi.\n\n"
            "Xotiramga muhrlanib qolgan bu voqea keyinchalik menga asqatdi. Biror keraksiz buyumni sotib olish vasvasasiga "
            "uchraganimda, o‘zimga: 'Hushtak uchun haddan ortiq haq to‘lama', — deyman-u, pulimni tejab qolaman. Voyaga yetib "
            "katta hayot yo‘liga qadam qo‘yganimdan keyin odamlarning xatti-harakatlarini kuzata boshladim. Shunda hushtagi juda "
            "qimmatga tushayotgan ko‘plab odamlarni uchratdim.\n\n"
            "Qirol saroyidagi qabulda ishtirok etish sharafiga noil bo‘lish yo‘lida o‘zining qimmatli vaqtini, farog‘atini, "
            "erkini, marhamatini va ehtimol, yor-do‘stlarini qurbon qilayotgan o‘ta izzattalab odamni ko‘rganimda o‘z-o‘zimga: "
            "'Bu kishining hushtagi juda qimmatga tushdi-da', — deb qo‘yardim. Shon-shuhratga haddan ziyod mukkasidan ketgan, "
            "doimiy ravishda siyosiy yugur-yugurlar bilan ovora bo‘lgan va e’tiborsizligi oqibatida kasb-korini o‘lda-jo‘lda "
            "qoldirgan kimsani ko‘rganimda esa: 'Chindan ham uning hushtagi juda qimmatga tushdi', — deb qo‘yar edim.\n\n"
            "Har qanday huzur-halovatdan, o‘zgalarga yaxshilik qilishdan, hamsoya hurmat-izzati, e’tiboridan va chin do‘stlik "
            "quvonchlaridan voz kechib, pul to‘plashni ixtiyor qilgan, o‘taketgan xasis odamni ko‘rganimda: 'Ey, baxtiqaro! "
            "Sening hushtaging naqadar qimmatga tushdi-ya', — derdim. Hissiy lazzat, kayfu safo yo‘lida aqlini qurbon qilgan "
            "va salomatligiga putur yetkazgan shahvatparastni uchratganimda, derdim: 'Sen adashyapsan, nazdingda lazzatdek "
            "tuyulayotgan narsa aslida bir darddir. Hushtaging juda qimmatga tushayapti!'\n\n"
            "O‘ziga oro berib, go‘zal liboslarga, chiroyli uylaru jihozlarga, foytunlarga mehr qo‘ygan, ammo ularga erishish "
            "uchun qo‘li kaltalik qilishi oqibatida qarzga botgan va umrini turmada nihoyalaganlarni ko‘rganimda: 'U hushtak "
            "uchun katta, juda katta to‘lov to‘ladi', — derdim. Xullasi kalom, men inson boshiga yog‘ilguvchi kulfatlarning "
            "ko‘p qismi odamlar narsalarning qimmatini to‘g‘ri baholay olmasliklaridan kelib chiqadi va ularning hushtagi "
            "juda qimmatga tushadi deb hisoblayman.\n\n"
            "Ammo har holda bunday baxtiqaroliklarga shafqatli bo‘lishimiz lozim. Holbuki, bunday o‘ylab qarasam, g‘ururlanishga "
            "arzigulik aql-farosatim borligiga qaramay, men uchun ham qirol Jonning olmalari kabi yo‘ldan ozdiruvchi narsalar "
            "bor. Xayriyatki, ularni sotib olib bo‘lmaydi. Bordi-yu, ular kimoshdi savdosiga qo‘yilganda men bir lahzada "
            "bor-yo‘g‘imdan ayrilishim va yana bir marta hushtak uchun haddan ziyod to‘lab yuborganimni payqamay qolishim "
            "mumkin bo‘lur edi.\n\n"
            "Ko‘rishguncha xayr, mening aziz do‘stim. Kamoli ehtirom ila sodiq qulingizdan deb bilursiz."
        )
        passage2 = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            title="Benjamin Franklin. Hushtak (Badiiy hikoya)",
            content=p2_content,
            order=2,
            source="Benjamin Franklin adabiy merosi",
        )

        p3_content = (
            "Alisher Navoiy. G‘azal\n\n"
            "1. G‘am toshin jismimda paykoning bila band aylading,\n"
            "   Ul samarni bu yig‘ochqa bargpayvand aylading.\n\n"
            "2. Chun shakar shirinlik izhor etti la’ling ollida,\n"
            "   Demayin, qilding tabassumkim, shakarxand aylading.\n\n"
            "3. Elga ishrat bodasi tuttung yoyib xoni visol,\n"
            "   Vahki, bizni qon yutub, g‘am yerga xursand aylading.\n\n"
            "4. Istamas bo‘lsang meni, bulbul kebi shaydo, nedin,\n"
            "   Yuzni gulgun boda birla gulga monand aylading.\n\n"
            "5. Qilding ul yuz jannatidin ayru bu ko‘z mardumin\n"
            "   Odamu har sari yoshin anga farzand aylading.\n\n"
            "6. Dahr bog‘ining gulida yo‘qturur bo‘yi vafo,\n"
            "   O‘zni, ey bulbul, agar parkand-parkand aylading.\n\n"
            "7. Ey pariy, debsen Navoiy bor emish Majnun kebi,\n"
            "   Bir yo‘li ul telbani qaydin xiradmand aylading.\n\n"
            "Lug'at izohlari:\n"
            "Paykon — o'q uchi, yor kipriklari.\n"
            "Bargpayvand — payvand qilish, bog'lash.\n"
            "Samar — meva, hosil.\n"
            "Shakarxand — chiroyli, shirin tabassum qiluvchi.\n"
            "Xoni — dasturxon (xoni visol — visol dasturxoni).\n"
            "Gulgun — gulrang, qip-qizil.\n"
            "Parkand — parcha-parcha, bo'lak-bo'lak.\n"
            "Qayd — bog'lanish, zanjir, to'siq.\n"
            "Xiradmand — oqil, dono, aql-idrokli."
        )
        passage3 = ReadingPassage.objects.create(
            test=test,
            section=sec_lit,
            title="Alisher Navoiy — G‘am toshin jismimda paykoning bila band aylading (G'azal)",
            content=p3_content,
            order=3,
            source="Alisher Navoiy, 'G'aroyib us-sig'ar' devoni",
        )

        # 7. Questions Data
        questions_spec = [
            # 1
            {
                "pos": 1,
                "section": sec_lang,
                "text": "Imloviy jihatdan NOTO`G`RI yozilgan so`zlar qatorini aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Ushbu qatordagi barcha so'zlar imlosida xatolik mavjud:\n"
                    "1. 'muxrdor' emas, 'muhrdor' (h harfi bilan);\n"
                    "2. 'taziya' emas, 'ta'ziya' (tutuq belgisi bilan);\n"
                    "3. 'shaddot' emas, 'shaddod' (oxiri d harfi bilan).\n\n"
                    "Eslab qoling: Arabcha o'zlashma so'zlarda 'h' va 'x' harflari hamda tutuq belgisi imlosiga alohida e'tibor bering."
                ),
                "choices": [
                    ("basirat, tamoshabin, jaxolat", False),
                    ("muxrdor, taziya, shaddot", True),
                    ("isloxot, menejment, ustomon", False),
                    ("me’ros, eksponat, tasarruf", False),
                ],
            },
            # 2
            {
                "pos": 2,
                "section": sec_lang,
                "text": "Imloviy jihatdan TO`G`RI yozilgan so`zlar qatorini aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. 'elektrobiologiya' (qo'shib yoziladi), 'falon-pismadon' (chiziqcha bilan), "
                    "'fayz-fazilat' (juft so'z, chiziqcha bilan) — barcha so'zlar qoidaga muvofiq to'g'ri yozilgan.\n"
                    "Boshqa variantlardagi xatolar: eran-qaran (chiziqchasiz berilgan), farruxjamol (ajratilgan), hali-hamon (chiziqchasiz)."
                ),
                "choices": [
                    ("elektrobiologiya, falon-pismadon, fayz-fazilat", True),
                    ("eran qaran, eshik-elik, farrux jamol", False),
                    ("fito - geografiya, galma-galdan, gaznasos", False),
                    ("gaz taqsimlagich, hali hamon, ifodaviy-tasviriy", False),
                ],
            },
            # 3
            {
                "pos": 3,
                "section": sec_lang,
                "text": (
                    "“Ko’k” so’zi (sifat ma'nosida) haqida berilgan fikrlarni tahlil qiling:\n"
                    "1) sinonimi — osmon;\n"
                    "2) antonimi — yer;\n"
                    "3) ko'chma ma'nosi — (ot).\n"
                    "Ushbu chizmadagi XATO fikrlarni aniqlang."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A (1, 2). 'Ko'k' so'zi sifat turkumida (masalan, ko'k maysa, ko'k ko'ylak) qo'llanganda, "
                    "uning sinonimi yoki antonimi ham sifat bo'lishi lozim. 'Osmon' va 'yer' esa ot turkumiga mansub. "
                    "Shuning uchun 1 va 2-fikrlar xatodir."
                ),
                "choices": [
                    ("1, 2", True),
                    ("3", False),
                    ("2, 3", False),
                    ("1", False),
                ],
            },
            # 4
            {
                "pos": 4,
                "section": sec_lang,
                "text": "O‘zaro ma’nodoshlik hosil qila oladigan so‘zlarni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. 'qo'rs', 'yoqimsiz', 'to'ng' so'zlarining barchasi bir xil so'z turkumiga (sifat) "
                    "mansub bo'lib, xarakter-xususiyatdagi qo'pollik va sovuqqonlikni ifodalovchi to'liq ma'nodoshlardir."
                ),
                "choices": [
                    ("qaror, jazm, azim", False),
                    ("yor, mahbuba, oshiq", False),
                    ("zehn, aqlli, zukko", False),
                    ("qo'rs, yoqimsiz, to'ng", True),
                ],
            },
            # 5
            {
                "pos": 5,
                "section": sec_lang,
                "text": "Qaysi qatorda qo‘shimcha qo‘llash bilan bog‘liq uslubiy xatolik MAVJUD?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. 'Ota bilan birga yotgan hamxonadoshlari...' jumlasida 'ham-' old qo'shimchasi hamda "
                    "'-dosh' orqa qo'shimchasi birgalik ma'nosini ortiqcha takrorlamoqda (pleonazm). 'Hamxona' yoki 'xonadosh' "
                    "shakllaridan biri ishlatilishi lozim edi."
                ),
                "choices": [
                    ("Shu kechasiyoq otani kasalxonaga olib borib yotqizishdi.", False),
                    ("Ota bilan birga yotgan hamxonadoshlari juda yaxshi insonlar ekan", True),
                    ("O’g’lim me’morlikni o’rgangan , otasidek sangtarosh bo’lib qolmasin dedim.", False),
                    ("Masalaga moddiy manfaatdorlik nuqtai nazaridan yondashmoq kerak.", False),
                ],
            },
            # 6
            {
                "pos": 6,
                "section": sec_lang,
                "text": "Qaysi gapda 'bitmoq' so’zi “muyassar bo'lmoq / nasib qilmoq” ma’nosida qo‘llangan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. 'Mana, xudo xohlasa, boshingga do’ppi, oyog’ingga etik, ko’ylak-ishton bitadi' "
                    "gapida 'bitadi' fe'li 'yetishadi, nasib etadi, muyassar bo'ladi' ko'chma ma'nosida qo'llangan."
                ),
                "choices": [
                    ("Tilak bilan bitmagan, bilim bilan bitar.", False),
                    ("Buyurdim erta-indin bitib qolar.", False),
                    ("Mana ,xudo xohlasa, boshingga do’ppi , oyog’ingga etik, ko’ylak-ishton bitadi.", True),
                    ("Azamga et bitib, rangiga qon yugurdi.", False),
                ],
            },
            # 7
            {
                "pos": 7,
                "section": sec_lang,
                "text": (
                    "So’z yasovchi qo’shimchalar haqida berilgan NOTO’G’RI ma’lumotni toping:\n"
                    "\"Shavkatli tariximizni zamonaviy, muhobatli tarixiy ishlar bilan boyitishga harakat qiling. "
                    "Uni har xil murtad talqinlardan, tuhmat va iflosliklardan tinimsiz tozalang.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Matnda 'iflosliklardan' (iflos sifatidan ot yasalgan) so'zi bor, biroq fe'ldan ot "
                    "yasovchi qo'shimcha ishtirok etmagan. Shuning uchun D fikr noto'g'ri."
                ),
                "choices": [
                    ("barcha sifatlar affiksatsiya usulida yasalgan", False),
                    ("fe’llar ikki o’rinda qo’shimcha qo’shish usuli bilan yasalgan.", False),
                    ("so’z yasalishi to’rt xil so’z turkumi doirasida kuzatilgan", False),
                    ("ot yasovchi qo’shimcha bir o’rinda sifatga, bir o’rinda fe’lga qo’shilgan.", True),
                ],
            },
            # 8
            {
                "pos": 8,
                "section": sec_lang,
                "text": (
                    "Har uchala parchada ishtirok etgan fe’l shakllarini aniqlang:\n"
                    "1. Kuchli raqib — qo’shni xondan / Maktub olmish O’g’izxon.\n"
                    "   Unda shunday bitib qo’yilmish: / “Tingla, so’zimni, ey xon”.\n"
                    "2. Yerimiz, suvimiz, farzandimiz deb, / Xotin, bola-chaqa, dilbandimiz deb,\n"
                    "   Birma-bir jonimiz etamiz fido, / Vatanni dushmanga bermaymiz aslo.\n"
                    "3. O’n olti martaba to’planib bizlar / Rejalar tortishdik yangi ishlarga,\n"
                    "   Nima deyishni bilmaydi dushman, / Bir reja bo’yicha yugurishlarga.\n"
                    "1) sodda yasama fe’l; 2) o’timli fe’l; 3) ravishdosh; 4) faqat to’ldiruvchi va kesim vazifasida kelgan; 5) kelasi zamon."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B (2, 3). 1-parchada: 'bitib' (ravishdosh), 'olmish' (o'timli fe'l); "
                    "2-parchada: 'deb' (ravishdosh), 'etamiz', 'bermaymiz' (o'timli fe'llar); "
                    "3-parchada: 'to'planib' (ravishdosh), 'tortishdik' (reja tortishdik — o'timli fe'l). "
                    "Demak, 2 (o'timli fe'l) va 3 (ravishdosh) uchala parchada ham mavjud."
                ),
                "choices": [
                    ("3, 4", False),
                    ("2, 3", True),
                    ("2, 4", False),
                    ("2, 5", False),
                ],
            },
            # 9
            {
                "pos": 9,
                "section": sec_lang,
                "text": (
                    "Ravish haqida XATO fikrni toping:\n"
                    "\"Ta’limning birinchi kunlaridayoq o’quvchilarni harflab emas, bo’g’inlab o’qishga o’rgatish kerak. "
                    "Har doim sohada ilgarigiga qaraganda yangiliklar berib borish, ta’lim oluvchini harakatga undash orqali "
                    "yuqori natijaga erishish kuzatiladi.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Matndagi ravishlar: 'harflab', 'bo'g'inlab' (holat ravishlari), 'har doim' va 'ilgari' "
                    "(payt ravishlari). Ravishning jami 2 ta ma'no turi qatnashgan. 'Uch turi berilgan' degan da'vo xatodir."
                ),
                "choices": [
                    ("ravishning ikki turi mavjud", False),
                    ("faqat hol vazifasida kelgan", False),
                    ("ikki o’rinda affiksatsiya usuli bilan, bir o’rinda kompozitsiya usuli bilan yasalgan", False),
                    ("ravishning uch turi berilgan", True),
                ],
            },
            # 10
            {
                "pos": 10,
                "section": sec_lang,
                "text": (
                    "Gap bo’laklari haqida XATO fikrni toping:\n"
                    "\"Qanoat aylagan shohi jahondir,\n"
                    "Tama qilgan eshakdan ham yomondir.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Gapning egalari: 'Qanoat aylagan' va 'Tama qilgan'. Ular so'z birikmasi "
                    "(qo'shma fe'lli sifatdosh birikmasi) bilan ifodalangan murakkab egalardir, yasama so'z emas. "
                    "Shuning uchun 'barcha ega yasama so'zdan iborat' degan fikr xato."
                ),
                "choices": [
                    ("barcha kesimlar ot kesim", False),
                    ("barcha ega yasama so’zdan iborat", True),
                    ("barcha egalar murakkab shaklda kelgan", False),
                    ("gapning barcha bosh bo’laklari otlashgan so’z bilan ifodalangan", False),
                ],
            },
            # 11
            {
                "pos": 11,
                "section": sec_lang,
                "text": (
                    "Gapdagi so‘zlarning mazmunan va grammatik jihatdan bog‘lanishlari to‘g‘ri ko‘rsatilgan javobni aniqlang:\n"
                    "\"Imtihonda tushgan qiziqarli testlarni ko’rib murakkab amaliyotlar tuzgim, ularni ipidan ignasigacha "
                    "o’rgatgim kelishini qo’l uchida bajarayotgan bola bilarmikan\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. 'qo’l uchida bajarayotgan' (ibora va sifatdosh o'rtasida holli bog'lanish) hamda "
                    "'murakkab amaliyotlar' (sifat va ot o'rtasida aniqlovchili bitishuvli bog'lanish) grammatik to'g'ri ko'rsatilgan."
                ),
                "choices": [
                    ("tuzgim, o’rgatgim kelishini, testlarni tuzgim kelishini", False),
                    ("ipidan ignasigacha, imtihonda ko’rib", False),
                    ("qo’l uchida bajarayotgan, murakkab amaliyotlar", True),
                    ("kelishini bilarmikan, muarkkab testlar", False),
                ],
            },
            # 12
            {
                "pos": 12,
                "section": sec_lang,
                "text": (
                    "Qaysi gaplarda tire belgisi o‘zaro bir xil punktuatsion qoida asosida qo‘yilgan?\n"
                    "1. Hayotning poyonsiz ummoni ichra / Bor shunday g‘ariblar — temirlar hissiz.\n"
                    "2. Muharrir mehri tovlanib: “Rahmat, ona qizim!” – dedi.\n"
                    "3. Vatan – bu sening onang\n"
                    "4. Sahnaga gul ko’targan qizchalar — gulchalar chiqdi."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B (1, 4). 1 va 4-gaplarda tire ajratilgan izohlovchi bo'lak ('temirlar hissiz', 'gulchalar') "
                    "oldidan qo'yilgan bo'lib, ikkalasida ham bir xil punktuatsion qoidaga amal qilingan."
                ),
                "choices": [
                    ("1, 3", False),
                    ("1, 4", True),
                    ("2, 3", False),
                    ("3, 4", False),
                ],
            },
            # 13
            {
                "pos": 13,
                "section": sec_lang,
                "text": (
                    "Quyidagi bayt haqida berilgan NOTO’G’RI fikrni aniqlang:\n"
                    "\"Nasihat ahli manga derki, mayni tark et, vah,\n"
                    "Ilig olib kelur, og‘iz ichar, manga ne gunah?\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Baytdagi qofiya: 'vah' va 'gunah'. Asosiy tovush (raviy) — 'h' undoshi. "
                    "Undosh tovush bilan tugagan qofiya esa aruz ilmida 'muqayyada' (bog'langan) deyiladi, "
                    "'mutlaqa' (unli bilan tugagan) emas. Shu sababli D xatodir."
                ),
                "choices": [
                    ("baytda tajohil ul-orif san’ati qo’llangan.", False),
                    ("baytda undosh tovushning raviy vazifasida kelishi kuzatiladi.", False),
                    ("baytda radif ishtirok etmagan.", False),
                    ("baytda mutlaq qofiya qo’llangan", True),
                ],
            },
            # 14
            {
                "pos": 14,
                "section": sec_lang,
                "text": (
                    "Quyidagi baytdan “Yo’ldosh”, “hamroh”, “ketma-ket” ma’nosini anglatuvchi badiiy unsurni toping:\n"
                    "\"Qaro ko’zum, kel-u, mardumliq endi fan qilg’il,\n"
                    "Ko’zum qarosida mardum kibi vatan qilg’il.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Baytda 'fan — vatan' so'zlari qofiyadosh bo'lib, 'mardum / mardumliq' tushunchasi "
                    "hamrohlik, ko'z qorachig'i va kishilik fazilatini mujassam etadi."
                ),
                "choices": [
                    ("qilg’il — radif", False),
                    ("fan — vatan — qofiya", True),
                    ("“n” tovushi — raviy", False),
                    ("qaro — tajnis", False),
                ],
            },
            # 15
            {
                "pos": 15,
                "section": sec_lang,
                "text": (
                    "Quyidagi qaysi voqealar Said Ahmadning “Ufq” romaniga MANSUB EMAS?\n"
                    "1. Yiqqan mol-davlatini bir kechada o’g’rilar o’g’irlab ketgan Inoyat oqsoqol obrazi uchraydi;\n"
                    "2. O’z singlisini o’ldirgan Akbarali Azizxon tarafidan o’ldiriladi;\n"
                    "3. Farg’ona kanali qurilishida Azizxonga yordam bergan Jo’ra polvon urushda halok bo’ladi;\n"
                    "4. Nizomjon otasidan qolgan merosni o’ziga olmasdan Yozyovonda tashkil etiladigan kolxoz xo’jaligiga topshirgan;\n"
                    "5. Xolmatjonning sinfdoshi bo’lgan Dildora A’zamjonga turmushga chiqadi;\n"
                    "6. Kuyganyordagi majlisda Azizxon Esh polvonni bir nojo’ya gapi uchun o’rindig’i bilan birga ko’tarib otvoradi."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C (1, 2, 3, 5). Inoyat oqsoqol Cho'lponning 'Kecha va kunduz' romaniga mansub (1). "
                    "Akbarali va uning fojiasi boshqa kontekstda (2). Jo'ra polvon va Dildoraga doir detallar (3, 5) ham "
                    "'Ufq' syujetiga mos emas."
                ),
                "choices": [
                    ("1, 3, 4, 6", False),
                    ("2, 4, 5", False),
                    ("1, 2, 3, 5", True),
                    ("2, 3, 6", False),
                ],
            },
            # 16
            {
                "pos": 16,
                "section": sec_lang,
                "text": "Chingiz Aytmatovning “Qiyomat” (Plaxa) asari haqida TO’G’RI ma’lumotni toping:",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. 'Qiyomat' asarida Bo'ston va Akbara-Toshchaynarlar oilasi o'rtasidagi fojia, "
                    "insonning tabiatga nohaq tajovuzi (bo'ri bolasining uyadan to'zg'itilishi) ikki tomonlama fojia keltirishi markaziy o'rinda turadi."
                ),
                "choices": [
                    ("ushbu asarda tabiat maxluqlari bo`lmish jonivorlarning uyasini to`zg`itganligi ham o`zining, ham boshqa bir oilaning fojiasiga sabab bo`lgan obraz tasviri uchraydi.", True),
                    ("ushbu asarda bizning yagona haqiqiy dushmanimiz – odam. Odamdan xalos bo`lsak, mehnatlarimizning barcha mevalari bizning mulkimizga aylanadi…” deya barcha hayvonlarni isyonga da`vat qigan bo’ri obrazi uchraydi", False),
                    ("ushbu quloq” bo`lib, vaqti-vaqti bilan “tozalash” o`tkazib turgan va o`z farzandini ham shunga undagan obraz uchraydi.", False),
                    ("ushbu asarda otasining tavsiyasi bilan diniy maktabda o’qishni boshlagan , urushdan qaytib kelgandan so’ng eski diniy aqidalardan voz kechib, yangicha fikrlarni ilgari surgan va shu qarashlar tufayli seminariyadan haydalgan obraz uchraydi", False),
                ],
            },
            # 17
            {
                "pos": 17,
                "section": sec_lang,
                "text": (
                    "Otasi va bobosiga xos yurtsevarlik, erksevarlik, insoniy g’urur, o’zlikni anglash hissi unga butunlay begona, "
                    "unga ota-bobolaridan faqatgina mehnatsevarlik hislatigina meros bo’lib qolgan. Sotsialistik tizimda voyaga yetgan, "
                    "o’ziga xos manqurt bir kimsa bo’lib faqat sadoqat bilan xizmat qilishni biladigan obraz (Dehqonqul) qaysi asarda uchraydi?"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Ushbu xarakteristika Tog'ay Murodning 'Otamdan qolgan dalalar' romanidagi bosh qahramon "
                    "Dehqonqul obraziga tegishlidir."
                ),
                "choices": [
                    ("Asrni qaritgan kun", False),
                    ("Tushda kechgan umrlar", False),
                    ("Ming bir jon", False),
                    ("Otamdan qolgan dalalar", True),
                ],
            },
            # 18
            {
                "pos": 18,
                "section": sec_reading,
                "passage": passage1,
                "text": "Bakteriyalar matniga ko'ra, quyidagi qaysi ma’lumot TO’G’RI?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. Matnning III qismida aniq ta'kidlangan: 'Bakteriya sporalari yuqori temperatura va "
                    "zaharli moddalar taʼsiriga juda bardoshli.'"
                ),
                "choices": [
                    ("o’simliklar oqsillarni hayvonlarning azotli birikmalaridan hosil qiladi", False),
                    ("bakteriyalar oval va aylana shakllar hosil qila oladi", False),
                    ("bakteriya sporalari yuqori haroratga chidamli bo’ladi", True),
                    ("bakteriyalar kurtaklanish va bo’linish yo’li bilan ko’payadi", False),
                ],
            },
            # 19
            {
                "pos": 19,
                "section": sec_reading,
                "passage": passage1,
                "text": "Bakteriyalar matniga ko'ra, quyidagi qaysi ma’lumot NOTO’G’RI?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Matnda: 'Bakteriya yuqori temperaturaga, odatda, chidamsiz, quritish, oftob, har xil "
                    "kimyoviy moddalar bakteriyani oʻldiradi' deyilgan. Shu bois 'bakteriyalar har qanday haroratda o'z "
                    "yashovchanligini saqlab qoladi' degan fikr xatodir."
                ),
                "choices": [
                    ("bakteriyalarning paydo bo’lishi va rivojlanish sikli bir xilda kechmaydi", False),
                    ("bakteriyalar har qanday haroratda o’z yashovchanligini saqlab qola oladi", True),
                    ("patogen va fitopatogen bakteriyalar kasallik qo’zg’atuvchi bakteriyalar guruhiga kiradi.", False),
                    ("ayrim oqsillarning ammiakka aylanishida bakteriyalarning ta’siri bor", False),
                ],
            },
            # 20
            {
                "pos": 20,
                "section": sec_reading,
                "passage": passage1,
                "text": "Matnning ajratib ko’rsatilgan qaysi qismida paronimni noto'g'ri qo’llash bilan bog’liq uslubiy xatolik bor?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A (I qism). I qismda 'urug'dosh' so'zi qarindosh/turkumdosh ma'nosida noo'rin qo'llangan."
                ),
                "choices": [
                    ("I", True),
                    ("II", False),
                    ("III", False),
                    ("IV", False),
                ],
            },
            # 21
            {
                "pos": 21,
                "section": sec_reading,
                "passage": passage1,
                "text": "Bakteriyalar matni mazmuniga quyidagi qaysi ma’lumot MOS EMAS?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Matnda ular 'makroorganizmlar' emas, 'bir hujayrali mikroorganizmlar' deb atalgan."
                ),
                "choices": [
                    ("buralgan, sharsimon, ipsimon makroorganizmlar ham bakteriyaga kiritilgan", True),
                    ("tayoqchasimon bakteriyalarning uchi bir xil shaklda bo’lmaydi", False),
                    ("muhitning qulayligi sporalarda ayrim hujayralarning paydo bo’lishiga olib keladi", False),
                    ("mikrotsistalarning vujudga kelishi miksobakteriyalarning tarkibidagi vegitativ hujayralar bilan bo’g’liq", False),
                ],
            },
            # 22
            {
                "pos": 22,
                "section": sec_reading,
                "passage": passage1,
                "text": "Quyidagi qaysi ma’lumot Bakteriyalar matni mazmuniga mos?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Matnning III qismida yuqori harorat bakteriyalarni nobud qilishi ta'kidlangan."
                ),
                "choices": [
                    ("bakteriyalarning nobud bo’lishiga haroratning yuqoriligi sabab bo’ladi", True),
                    ("kislorodli muhitda energiya ajralib chiqishi qulay bo’ladi", False),
                    ("ko’ndalang shakldagi bo’linishdan hujayra xaltasi paydo bo’ladi", False),
                    ("sitoplazmada joylashgan ribosamalarni RNK tarkibida ham uchratishimiz mumkin", False),
                ],
            },
            # 23
            {
                "pos": 23,
                "section": sec_reading,
                "passage": passage2,
                "text": "Benjamin Franklinning “Hushtak” hikoyasi haqida berilgan TO’G’RI fikrni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Hikoyanavis oxirida o'zi ham ehtiyotsizlik qilib, 'qirol Jonning olmalari kabi' "
                    "narsalarga uchib, yoshligidagi kabi yana bir bor hushtak uchun haddan ortiq haq to'lab yuborishi "
                    "mumkinligini kamtarlik bilan e'tirof etadi."
                ),
                "choices": [
                    ("hikoyanavis janob B. ga o’zining boshidan o’tgan ibratli hikoyani aytib berish orqali hayotda arzimagan narsalarga ko’p pul sarflamaslik kerakligini uqtiradi.", False),
                    ("hikoyanavis insonlar o’z vaqti va boyliklarini juda qimmat narsalarga sarf etayotganliklarini aytadi.", False),
                    ("hikoyanavis “ko’rpangga qarab oyoq uzat” maqoli asosida odamlar o’z iqtisodini o’ylab ish qilishi kerakligi g’oyasini hikoyasiga singdirib yuboradi.", False),
                    ("hikoyanavis “o’rgangan ko’ngil o’rtansa qo’ymas” deganlaridek , yoshlikda qilgan xatosini yana takrorlashi mumkinligini aytib o’tadi.", True),
                ],
            },
            # 24
            {
                "pos": 24,
                "section": sec_reading,
                "passage": passage2,
                "text": "“Hushtak” hikoyasi haqida berilgan NOTO’G’RI fikrni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Hikoyada insonlar haqiqiy hushtak sotib olishmaydi, balki hushtak bu yerda "
                    "mansabparastlik, shon-shuhrat, qimmatbaho ashyolar va havoyi orzularning ramzidir."
                ),
                "choices": [
                    ("hikoyada insonlar bosh qahramon kabi hushtak sotib olishga juda ko’p mablag’ sarf etishayotganligi aytilgan.", True),
                    ("hikoyada insonlar keraksiz narsalarga vaqtlarini va bisotlarini sarf etishmaganida ko’proq narsaga erishishlari mumkinligi aytilgan.", False),
                    ("hikoyada yovuzlikning yo’qolishiga ham “hushtaklar” uchun kamroq to’lov qilish sabab bo’lishi mumkinligi aytilgan.", False),
                    ("hikoyada bosh qahramon xotirasiga muhrlanib qolgan voqea keyinchalik uning hayoti davomida asqotganligini kuzatish mumkin.", False),
                ],
            },
            # 25
            {
                "pos": 25,
                "section": sec_reading,
                "passage": passage2,
                "text": "Hikoya bosh qahramoni haqida berilgan quyidagi qaysi fikr NOTO’G’RI?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Bosh qahramon o'zining mutlaq xatosiz emasligini, hayotda yana xato qilib "
                    "qo'yish ehtimoli borligini ochiq aytadi. Shuning uchun 'bir xatoni ikkinchi bor takrorlamaydigan inson' degan hukm noto'g'ri."
                ),
                "choices": [
                    ("bir xatoni ikkinchi bor takrorlamaydigan inson.", True),
                    ("xatosidan to’g’ri xulosa chiqara oladigan, ammo yana shu xatoni qaytarishi mumkin bo’lgan inson", False),
                    ("ko’pchilik bolalar kabi yoshligida e’tiborni tortadigan arzimas narsalarga ham qiziqadigan inson", False),
                    ("boshqa odamlarning xatolarini kuzatib xulosa chiqara oladigan inson.", False),
                ],
            },
            # 26
            {
                "pos": 26,
                "section": sec_reading,
                "passage": passage2,
                "text": "Hikoyadagi 'hushtak' badiiy detali orqali yozuvchi nimaga ishora qilgan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Muallif 'hushtak' orqali insonning arzimagan narsalar ketidan quvib sarflagan vaqti, "
                    "boy bergan huzur-halovati, erki va butun umriga majoziy ishora qilgan."
                ),
                "choices": [
                    ("bekorchi narsalarga", False),
                    ("yo’qotilgan vaqtga", False),
                    ("inson hayotiga", False),
                    ("barchasi to’g’ri", True),
                ],
            },
            # 27
            {
                "pos": 27,
                "section": sec_reading,
                "passage": passage2,
                "text": "Hikoyaning boshida ajratib ko’rsatilgan parcha orqali bosh qahramonga xos qanday jihat yuzaga chiqqan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. Do'stining maktublariga o'z vaqtida javob yozish mas'uliyati, uning oldidagi "
                    "majburiyat va yuksak hurmat tuyg'usi bosh qahramonni qalam tebratishga undaydi."
                ),
                "choices": [
                    ("kattalarga hurmat-ehtiromli ekanligi", False),
                    ("to’g’ri fikrli insonlarga yaxshi munosabatda bo’lishi", False),
                    ("majburiyat va hurmat", True),
                    ("o’zi bilan bir xil fikrlaydiganlarni haddan tashqari hurmat qilish", False),
                ],
            },
            # 28
            {
                "pos": 28,
                "section": sec_lit,
                "passage": passage3,
                "text": (
                    "Alisher Navoiy g’azali matla’si haqida berilgan TO’G’RI fikrni aniqlang:\n"
                    "\"G‘am toshin jismimda paykoning bila band aylading,\n"
                    "Ul samarni bu yig‘ochqa bargpayvand aylading.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Ikkinchi misrada 'Ul samarni (paykonni / mevani) bu yig'ochqa (oshiqning jismiga) "
                    "bargpayvand aylading' deyilgan. Demak, oshiqning zaif jismi yog'ochga qiyoslangan."
                ),
                "choices": [
                    ("baytda yorning kiprigi mevaga qiyoslangan.", False),
                    ("baytda oshiqning jismi yog’ochga qiyoslangan.", True),
                    ("baytda g’am toshi payvandga qiyoslangan.", False),
                    ("baytda yorning qahri qattiqligi toshga qiyoslangan.", False),
                ],
            },
            # 29
            {
                "pos": 29,
                "section": sec_lit,
                "passage": passage3,
                "text": "G’azalning 2- va 3-baytlari haqida berilgan NOTO’G’RI fikrni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. 3-baytda: 'Vahki, bizni qon yutub, g‘am yerga xursand aylading' deyiladi. "
                    "Yor oshiqni visol dasturxoniga emas, g'am yeb qon yutadigan yerga mahkum etgan. Oshiq xursand emas, balki bu yorning sitamidir."
                ),
                "choices": [
                    ("baytda yorning labi shakardan ham shirin ekanligiga ishora qilingan.", False),
                    ("baytda oshiq qon yutayotgan bo’lsa ham yor yozgan dasturxon atrofida bo’lganidan xursand.", True),
                    ("baytda shakarning shirin ekanligini eshitib jilmayib qo’ygan yor holati tasvirlangan.", False),
                    ("baytda o’zga oshiqlar yor vasliga yetganligi aytilgan.", False),
                ],
            },
            # 30
            {
                "pos": 30,
                "section": sec_lit,
                "passage": passage3,
                "text": (
                    "G’azalning 5-bayti haqida berilgan TO’G’RI fikrni aniqlang:\n"
                    "\"Qilding ul yuz jannatidin ayru bu ko‘z mardumin\n"
                    "Odamu har sari yoshin anga farzand aylading.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Baytda ko'z qorachig'i (mardum) jannatdan quvilgan Odam Atoga, to'kilayotgan "
                    "ko'zyosh tomchilari esa uning farzandlariga badiiy tashbih qilingan."
                ),
                "choices": [
                    ("baytda ko’z qorachig’i odamga, ko’zyoshlar esa bolaga qiyoslangan.", True),
                    ("baytda yor yuzi jannatga, oshiq esa odamga qiyoslangan.", False),
                    ("baytda yor yuzidan ayrilgan ko’zning bola kabi ko’zyosh to’kayotganligi aytilgan.", False),
                    ("baytda oshiq yor yuzini ko’rish orqali jannatga erishishni niyat qilgan.", False),
                ],
            },
            # 31
            {
                "pos": 31,
                "section": sec_lit,
                "passage": passage3,
                "text": "Alisher Navoiy g’azali haqida berilgan NOTO’G’RI fikrni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. 4-baytda: 'Yuzni gulgun boda birla gulga monand aylading' misrasida yuzni qizil may bilan "
                    "gulga o'xshatgan shaxs oshiq emas, balki bevafo yorning o'zidir. Shu sababli A fikr noto'g'ri."
                ),
                "choices": [
                    ("baytlarning birida oshiq yorining e’tiborini tortish uchun o’zining yuzini qizil sharob bilan atay gulga o’xshatganligi aytilgan.", True),
                    ("baytlarning birida yor kipriklari oshiqqa g’am olib kelganligi aytilgan.", False),
                    ("baytlarning birida oshiq ko’zi yor yuzini ko’rishdan mahrum bo’lganligi uchun ham yig’layotganligi aytilgan.", False),
                    ("baytlarning birida yor oshig’ini telba deb hisoblashi aytilgan.", False),
                ],
            },
            # 32
            {
                "pos": 32,
                "section": sec_lit,
                "passage": passage3,
                "text": (
                    "G’azalning 6-baytida qanday mazmun ifodalangan?\n"
                    "\"Dahr bog‘ining gulida yo‘qturur bo‘yi vafo,\n"
                    "O‘zni, ey bulbul, agar parkand-parkand aylading.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Ushbu baytda bu foniy dunyo (dahr) go'zallarida vafo yo'qligi, oshiq (bulbul) "
                    "o'zini parcha-parcha qilsa ham vafosizlikka uchrashi uqtirilib, bulbul ogohlantirilmoqda."
                ),
                "choices": [
                    ("baytda bu dunyodagi go’zallarda vafo yo’q ekanligidan bulbul ogohlantirilgan.", True),
                    ("baytda oshiq yelib-yugursa ham yorlarning unga e’tibori yo’q ekanligi aytilgan", False),
                    ("baytda vafosizlik g’oyasi ifodalangan.", False),
                    ("baytda gulga yetishish uchun bulbul o’zini parcha-parcha qilishi kerakligi aytilgan", False),
                ],
            },
            # 33 (Matching item 33)
            {
                "pos": 33,
                "section": sec_lang,
                "text": (
                    "Gaplar (33, 34, 35) va sintaktik tahlilga oid izohlar (A – E) ni o'zaro to'g'ri moslashtiring:\n\n"
                    "33-gap: \"Bilimsizlik kulfat keltiradi, do’stim.\"\n\n"
                    "Ushbu gap uchun mos keluvchi sintaktik izohni tanlang:"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. 'Bilimsizlik' — ega, 'kulfat keltiradi' — kesim, 'do'stim' — vergul bilan ajratilgan undalma. "
                    "Demak, gap: 'undalma qatnashgan egali gap'."
                ),
                "choices": [
                    ("A) ajratilgan bo’lak", False),
                    ("B) shaxsi ma’lum gap", False),
                    ("C) undalma qatnashgan egali gap", True),
                    ("D) ritorik so’roq gapli qo’shma gap", False),
                    ("E) so’roq-undov gap", False),
                ],
            },
            # 34 (Matching item 34)
            {
                "pos": 34,
                "section": sec_lang,
                "text": (
                    "Gaplar (33, 34, 35) va sintaktik tahlilga oid izohlar (A – E) ni o'zaro to'g'ri moslashtiring:\n\n"
                    "34-gap: \"Yo’lim boshladi to kezdim dala-tog’,\n"
                    "          Kezdim ne yurtlarni — chiroyli tengsiz\"\n\n"
                    "Ushbu gap uchun mos keluvchi sintaktik izohni tanlang:"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. 'chiroyli tengsiz' birikmasi tire bilan ajratilib, 'ne yurtlarni' to'ldiruvchisining "
                    "belgisini aniqlashtiruvchi ajratilgan bo'lak vazifasida kelgan."
                ),
                "choices": [
                    ("A) ajratilgan bo’lak", True),
                    ("B) shaxsi ma’lum gap", False),
                    ("C) undalma qatnashgan egali gap", False),
                    ("D) ritorik so’roq gapli qo’shma gap", False),
                    ("E) so’roq-undov gap", False),
                ],
            },
            # 35 (Matching item 35)
            {
                "pos": 35,
                "section": sec_lang,
                "text": (
                    "Gaplar (33, 34, 35) va sintaktik tahlilga oid izohlar (A – E) ni o'zaro to'g'ri moslashtiring:\n\n"
                    "35-gap: \"Bo’lmasa xudo osmondan tashlarmidi?\"\n\n"
                    "Ushbu gap uchun mos keluvchi sintaktik izohni tanlang:"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. 'Bo'lmasa' (shart ergash gap vositasi) va 'xudo osmondan tashlarmidi?' (javob talab qilmaydigan ritorik so'roq gap) "
                    "birikib, ritorik so'roqli ergashgan qo'shma gapni hosil qilgan."
                ),
                "choices": [
                    ("A) ajratilgan bo’lak", False),
                    ("B) shaxsi ma’lum gap", False),
                    ("C) undalma qatnashgan egali gap", False),
                    ("D) ritorik so’roq gapli qo’shma gap", True),
                    ("E) so’roq-undov gap", False),
                ],
            },
            # 36
            {
                "pos": 36,
                "section": sec_lang,
                "text": (
                    "Ajratib ko’rsatilgan har uchala so’z bilan birika oladigan so’zni yozing:\n"
                    "1. Davramizdan yaqin do’stimiz ketti.\n"
                    "2. Etagi eshik o’rtasiga qisilib qoldi.\n"
                    "3. Beda ichi juda issiq, go’yoki quyoshning butun olovi yashiringanday.\n\n"
                    "(Diqqat: 'Davramizdan', 'o'rtasiga', 'ichi' so'zlari o'rniga sinonimik birika oladigan o'zak so'zni yozing)"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "ora | orasi | orasidan | orasiga",
                "explanation": (
                    "To'g'ri javob: 'ora' (yoki 'orasi'). 'Davramiz orasidan', 'eshik orasiga', 'beda orasi' "
                    "shaklida har uchala so'z bilan birikib, ma'nodoshlik hosil qiladi."
                ),
            },
            # 37
            {
                "pos": 37,
                "section": sec_lang,
                "text": (
                    "Berilgan gapda qo’llanilishi lozim bo’lgan tinish belgilarining to’g’ri ketma-ketligini yozing:\n\n"
                    "\"Yaxshining yaxshiligini aytingki nuri toshsin yomonning yomonligini aytingki quti o’chsin\"\n\n"
                    "Misol: vergul, vergul, vergul, nuqta"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "vergul, vergul, vergul, nuqta | vergul, nuqtali vergul, vergul, nuqta",
                "explanation": (
                    "Ketma-ketlik: 'aytingki,' (1-vergul) 'toshsin,' yoki nuqtali vergul (2-tinish belgisi) "
                    "'aytingki,' (3-vergul) 'o'chsin.' (4-nuqta)."
                ),
            },
            # 38
            {
                "pos": 38,
                "section": sec_lang,
                "text": (
                    "Gapda qaysi qo‘shimcha qo‘llash bilan bog‘liq uslubiy xatolik kuzatilgan?\n\n"
                    "\"Olamning cheksiz sirlarini bilish, inson ehtiyojlarini borliqqa moslashtirish va uni "
                    "o’zgartirilishga bo’ysundirishda aqlga teng keladigan kuch yo’q.\""
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "-il | -il- | majhul nisbat | majhul nisbat qo'shimchasi",
                "explanation": (
                    "Uslubiy xatolik 'o'zgartirilishga' so'zida -il majhul nisbat qo'shimchasining ortiqcha qo'llanishidir. "
                    "Inson subyekt bo'lganligi sababli 'o'zgartirishga' (aniq nisbat) bo'lishi lozim edi."
                ),
            },
            # 39
            {
                "pos": 39,
                "section": sec_lang,
                "text": (
                    "Gapdagi so‘zlarning mazmunan va grammatik jihatdan bog‘lanishlarini tahlil qiling:\n"
                    "\"Bu — Alif, zamon va makon, butun borliqni o’z ichiga olgan nuqta.\"\n\n"
                    "Javobni quyidagi formatda yozing: a) [so'z] b) [so'z]\n"
                    "a) gapda ajratib ko‘rsatilgan 'nuqta' so‘ziga tobelanib bog‘langan so‘zni yozing;\n"
                    "b) 'nuqta' so‘zi bilan teng munosabatda bog‘langan so‘zni yozing."
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "a) olgan b) Alif | olgan, Alif | olgan; Alif | a) o'z ichiga olgan b) Alif",
                "explanation": (
                    "a) 'olgan' sifatdoshi 'nuqta' otiga aniqlovchi bo'lib tobelanib bog'langan;\n"
                    "b) 'Alif' va 'nuqta' so'zlari uyushiq ot-kesimlar bo'lib, o'zaro teng munosabatda bog'langan."
                ),
            },
            # 40
            {
                "pos": 40,
                "section": sec_lang,
                "text": (
                    "Berilgan gapdagi ajratilgan sintaktik birlikni nomlang:\n\n"
                    "\"Kechqurun, ona choy ichib o’tirganda, tanish bir odamning ovozi keldi.\""
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "ajratilgan hol | ajratilgan payt holi | ajratilgan bo'lak",
                "explanation": (
                    "'ona choy ichib o'tirganda' birikmasi vergullar bilan ajratilgan hol (ajratilgan payt holi) bo'lib, "
                    "'Kechqurun' payt holining ma'nosini aniqlashtirib kelgan."
                ),
            },
            # 41
            {
                "pos": 41,
                "section": sec_lang,
                "text": (
                    "Berilgan gaplarni grammatik jihatdan tahlil qiling:\n"
                    "1. Biz siz uchun izlanib test tuzyapmiz\n"
                    "2. Siz esa erinchoqlik bilan ishlayapsiz\n"
                    "3. Natijangiz sira ko’tarilmaydi\n\n"
                    "Javobni quyidagi formatda yozing: a) [vosita] b) [mazmun]\n"
                    "a) ikkinchi va uchinchi gapni qanday grammatik vosita yordamida to’g’ri bog’lash mumkin?\n"
                    "b) gaplar orasida qanday mazmun ifodalangan?"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "a) shuning uchun b) sabab-oqibat | shuning uchun, sabab-oqibat | a) -sa b) shart-oqibat",
                "explanation": (
                    "a) 'Siz esa erinchoqlik bilan ishlayapsiz, shuning uchun natijangiz sira ko'tarilmaydi' — bog'lovchi vazifasidagi so'z: 'shuning uchun' (yoki '-sa');\n"
                    "b) gaplar o'rtasida 'sabab-oqibat' (sabab va natija) mazmuni ifodalangan."
                ),
            },
            # 42
            {
                "pos": 42,
                "section": sec_lit,
                "text": (
                    "Quyidagi savollarga javob yozing (Format: a) [san'at] b) [san'at]):\n\n"
                    "1. Topilmas husn mulkinda senga teng bir qamar manzar,\n"
                    "   Na manzar? Manzari shohid. Na shohid? Shohidi dilbar\n\n"
                    "2. Yordin ayru ko’ngul mulkedurur sultoni yo’q,\n"
                    "   Mulkkim sultoni yo’q, jismedururkim, joni yo’q\n\n"
                    "a) birinchi baytda qo’llangan she’riy san’atning nomini aniqlang;\n"
                    "b) ikkinchi baytda qo’llangan she’riy san’atning nomini aniqlang."
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "a) savol-javob b) taddi | savol-javob, taddi | a) suol-javob b) tasdir | savol-javob, tasdir",
                "explanation": (
                    "a) 1-baytda shoir 'Na manzar? ... Na shohid? ...' orqali o'ziga savol berib o'zi javob qaytargan: savol-javob (suol-javob) san'ati;\n"
                    "b) 2-baytda birinchi misra oxiridagi so'z ikkinchi misra boshida takrorlangan ('sultoni yo'q, Mulkkim sultoni yo'q'): taddi (tasdir / raddu-l-ajuz alats-sadr) san'ati."
                ),
            },
            # 43
            {
                "pos": 43,
                "section": sec_lit,
                "text": (
                    "Quyidagi savollarga javob yozing (Format: a) [tovush] b) [qofiya turi]):\n\n"
                    "\"Ish manga qilmoqdurur ul sho‘xi beparvoni yod,\n"
                    " Ul unutmish anikim, qilg‘ay meni shaydoni yod.\"\n\n"
                    "a) yuqoridagi baytda qofiyadosh so’zlardagi tirgak tovushni aniqlang;\n"
                    "b) yuqoridagi baytda raviyning o’rniga ko’ra qofiya turini aniqlang."
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "a) o b) mutlaqa | a) alif b) mutlaqa | o, mutlaqa | alif, mutlaqa",
                "explanation": (
                    "Qofiyadosh so'zlar: 'beparvo' va 'shaydo', radif: 'yod'.\n"
                    "a) qofiya asosidagi cho'ziq unli 'o' (alif) tirgak vazifasini o'taydi;\n"
                    "b) unli tovush bilan tugaganligi sababli raviyning o'rniga ko'ra qofiya turi: 'mutlaqa' (ochiq qofiya)."
                ),
            },
            # 44
            {
                "pos": 44,
                "section": sec_lit,
                "text": (
                    "Quyidagi savollarga javob yozing (Format: a) [janr] b) [qofiya va radif]):\n\n"
                    "\"Yo rabki, inoyatingni yor ayla manga,\n"
                    " Yo‘qluqqa hidoyatingni bor ayla manga,\n"
                    " Ham kahfi kifoyatingni dor ayla manga,\n"
                    " Ham durri inoyating nisor ayla manga.\"\n\n"
                    "a) yuqoridagi she’r janrini aniqlang;\n"
                    "b) yuqoridagi she’rning qofiyalanish tartibi va radif turi qanday?"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "a) ruboiy b) a-a-a-a, murakkab radif | ruboiy, a-a-a-a | ruboiy, musalsal",
                "explanation": (
                    "a) Janri: Ruboiy (munojot mavzusidagi to'rtlik);\n"
                    "b) Qofiyalanish tartibi: a-a-a-a (barcha misralar qofiyalangan musalsal qofiya). "
                    "Radif turi: 'ayla manga' ikki mustaqil so'zdan iborat bo'lgani uchun murakkab radif hisoblanadi."
                ),
            },
            # 45 (Written / Essay)
            {
                "pos": 45,
                "section": sec_writing,
                "text": (
                    "ESSE TOPSHIRIG'I (BMB Milliy Sertifikat 12 mezonli rasmiy formati):\n\n"
                    "Mavzu: Ayni paytda o’quvchilarni o’rta maktablarga to’liq jalb qilish maqsadida maxsus ishchi guruh "
                    "ishlayapti. Ayrimlar ta’lim sifatini oshirish uchun tizim ishlab chiqilishi tarafdori. Nima deb o’ylaysiz, "
                    "dars sifatining yaxshilanishi orqali davomatga ijobiy ta’sir etish mumkinmi?\n\n"
                    "Qo'yiladigan rasmiy talablar:\n"
                    "1. Fikr-mulohazalaringizni publitsistik uslubda, mantiqiy izchillikda va adabiy til me’yorlariga amal qilgan holda bayon qiling.\n"
                    "2. Esse uch tarkibiy qismdan iborat bo’lishi lozim:\n"
                    "   I. Kirish: 2-3 jumladan iborat bo'lsin, berilgan vaziyat matnini aynan ko'chirmang;\n"
                    "   II. Asosiy qism: kamida uchta xatboshidan iborat bo'lsin, har bir xatboshida tomonlarning va shaxsiy qarashlaringizni hayotiy misollar va dalillar bilan yoriting;\n"
                    "   III. Xulosa: asosiy qismdagi fikrlarni umumlashtiruvchi 2-3 jumla bo'lsin.\n"
                    "3. Reja tuzilmaydi, epigraf qo'yilmaydi.\n"
                    "4. Minimal hajm: 200 so'z (maksimal: 500 so'z)."
                ),
                "type": Question.QuestionType.WRITTEN,
                "points": 25,
                "config": {
                    "min_words": 200,
                    "max_words": 500,
                    "rubric": "bmb_12_mezon",
                    "national_cert_scale": True,
                },
                "explanation": (
                    "Esse BMB rasmiy 12 ta mezoni bo'yicha baholanadi:\n"
                    "1. Mavzuning to'liq ochilishi (2 ball)\n"
                    "2. Fikrning mantiqiy izchilligi va ketma-ketligi (2 ball)\n"
                    "3. Hayotiy va asosli dalillar keltirish (2 ball)\n"
                    "4. Publitsistik uslub me'yorlariga rioya qilish (2 ball)\n"
                    "5. Leksik boylik va so'z qo'llash mahorati (2 ball)\n"
                    "6. Sintaktik qurilmalarning xilma-xilligi va to'g'riligi (2 ball)\n"
                    "7. Imlo qoidalariga rioya etish (2 ball)\n"
                    "8. Tinish belgilarini o'z o'rnida qo'llash (2 ball)\n"
                    "9. Abzaslarga (xatboshilarga) to'g'ri bo'lish (2 ball)\n"
                    "10. Tarkibiy yaxlitlik (Kirish, Asosiy qism, Xulosa) (2 ball)\n"
                    "11. Mustaqil, xolis va teran dunyoqarash (2.5 ball)\n"
                    "12. Belgilangan hajm talabiga to'liq javob berish (2.5 ball)\n"
                    "Jami: 25 ball."
                ),
            },
        ]

        # 8. Insert Questions & Choices
        created_questions = 0
        created_choices = 0

        for q_data in questions_spec:
            q = Question.objects.create(
                test=test,
                section=q_data["section"],
                reading_passage=q_data.get("passage"),
                text=q_data["text"],
                question_type=q_data["type"],
                points=q_data["points"],
                position=q_data["pos"],
                explanation=q_data.get("explanation", ""),
                correct_text=q_data.get("correct_text", ""),
                config=q_data.get("config", {}),
            )
            created_questions += 1

            for c_idx, (choice_text, is_corr) in enumerate(q_data.get("choices", [])):
                Choice.objects.create(
                    question=q,
                    text=choice_text,
                    is_correct=is_corr,
                    position=c_idx + 1,
                )
                created_choices += 1

        # 9. Sync Standalone EssayTopic for Task 45
        essay_topic, topic_created = EssayTopic.objects.get_or_create(
            title="Maktablarda dars sifati va o'quvchilar davomati bog'liqligi (BMB Mock #4)",
            defaults={
                "description": (
                    "Ayni paytda o’quvchilarni o’rta maktablarga to’liq jalb qilish maqsadida maxsus ishchi guruh ishlayapti. "
                    "Ayrimlar ta’lim sifatini oshirish uchun tizim ishlab chiqilishi tarafdori. Nima deb o’ylaysiz, "
                    "dars sifatining yaxshilanishi orqali davomatga ijobiy ta’sir etish mumkinmi? Fikr-mulohazalaringizni "
                    "publitsistik uslubda 12 mezon asosida bayon qiling."
                ),
                "category": EssayTopic.Category.ONA_TILI,
                "word_limit_min": 200,
                "word_limit_max": 500,
                "time_limit_minutes": 60,
                "national_cert_scale": True,
                "sample_outline": (
                    "I. Kirish: Bugungi kunda o'quvchilar davomati va maktab ta'limi samaradorligi masalasining dolzarbligi.\n"
                    "II. Asosiy qism:\n"
                    "  - 1-qarash: Ma'muriy nazorat va cheklovlar davomatni oshira oladimi?\n"
                    "  - 2-qarash: Qiziqarli va sifatli dars — o'quvchini darsga jalb qiluvchi eng qudratli omil.\n"
                    "  - Shaxsiy fikr va hayotiy misol: O'qituvchining mahorati va zamonaviy metodlar ta'siri.\n"
                    "III. Xulosa: Ta'lim sifatini isloh qilish orqali davomat muammosini tabiiy va barqaror hal etish."
                ),
            },
        )
        if not topic_created and not essay_topic.national_cert_scale:
            essay_topic.national_cert_scale = True
            essay_topic.save(update_fields=["national_cert_scale"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded BMB Mock #4!\n"
                f"- Test ID: {test.id} ({test.title})\n"
                f"- Code: {test.mock_code}\n"
                f"- Time Limit: {test.time_limit_minutes} minutes\n"
                f"- Questions: {created_questions} questions (1..44 + 45 Esse)\n"
                f"- Choices: {created_choices} choices\n"
                f"- Reading Passages: 3 passages\n"
                f"- Sections: 4 sections (LANGUAGE, READING, LITERATURE, WRITING)\n"
                f"- Standalone Essay Topic: ID {essay_topic.id}"
            )
        )
