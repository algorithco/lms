"""
Django Management Command: seed_rash_mock_shukurov

Seeds the 3-hour official BMBA Mock Diagnostic Exam (Umid Shukurov jamoasi):
- 44 Test Questions (Grammar, Reading "O'lik dengiz", Story "Ming marta shukur", Classical Ghazal Navoiy, Syntactic Matching, Short Written)
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
    help = "Seeds BMBA Rasmiy Mock Test (Umid Shukurov jamoasi) into the platform."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing Shukurov Mock test before recreating.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        reset: bool = options.get("reset", False)
        self.stdout.write(self.style.NOTICE("Seeding BMBA Rasmiy Mock Test (Umid Shukurov jamoasi)..."))

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
        mock_code = "#MOCK-SHUKUROV"
        existing_test = Test.objects.filter(mock_code=mock_code).first()
        if not existing_test:
            # Also check without hash
            existing_test = Test.objects.filter(mock_code="MOCK-SHUKUROV").first()

        if existing_test and reset:
            self.stdout.write(self.style.WARNING("Reset requested: Deleting existing Shukurov Mock test..."))
            existing_test.delete()
            existing_test = None

        test_title = "Ona tili va Adabiyot — Rasmiy Mock Test (Umid Shukurov jamoasi)"
        test_desc = (
            "3 soatlik (180 daqiqa) rasmiy BMBA andozasidagi diagnostik imtihon. "
            "44 ta test topshirig'i, 'O'lik dengiz', 'Ming marta shukur' (Aziz Nesin), "
            "Navoiy g'azali tahlillari hamda nafaqa yoshi bo'yicha 12 mezonli publitsistik Esse."
        )

        if existing_test:
            test = existing_test
            test.title = test_title
            test.description = test_desc
            test.time_limit_minutes = 180
            test.difficulty = Test.Difficulty.HARD
            test.status = Test.Status.PUBLISHED
            test.pass_percentage = 60
            test.max_attempts = 0
            test.mock_code = mock_code
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
                title=test_title,
                description=test_desc,
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
            defaults={"name": "BMBA Rasmiy Esse", "order": 4, "weight": Decimal("1.00")},
        )

        # 6. Reading Passages
        p1_content = (
            "O‘LIK DENGIZ\n\n"
            "I QISM:\n"
            "Oʻlik dengiz “Lut dengizi”, “Tuz dengizi”, “Asfalt dengizi”, “Siddum dengizi” kabi nomlari bor. "
            "Strabon “Geografiya”sida “Sirbonid koʻli” deb atagan. Qurʻoni karimda Lut qavmining toʻfon ostida "
            "qolgani, bu qavm beshta shaharda yashagani haqida aytilgan. Qazishma ishlari qadimgi Sodom va Gomorra "
            "shaharlari koʻlining janubiy sohilidagi hozir faqat qum-tuproq uyumlarigina qolgan Siddim vodiysida "
            "joylashganini koʻrsatdi. Olmon arxeologi Verner Keller ham bu yerda juda qattiq zilzila boʻlgani, tabiiy "
            "gazlar portlab, chaqmoq tushgani, tevarak-atrof yongʻin ichida qolgani va Siddim vodiysini shaharlari "
            "bilan birga yer yutganini taʻkidlaydi. Vayron boʻlgan shaharlar haqida koʻlning sharqiy qismidagi suvosti "
            "manzaralari ham darak berib turganga oʻxshaydi. Koʻlning quyi oqimi boʻylab qayiqda kezilsa, quyosh nurlari "
            "mos tushgan paytlari suv ostidagi oʻrmonzorni koʻrish mumkin. Bu daraxtlarni suvdagi intensiv tuzlar qotirib qoʻygan.\n\n"
            "II QISM:\n"
            "Oʻlik dengiz shoʻr koʻllar ichida eng chuquridir. Dengiz sohili Yerning quruqlik qismidagi eng quyi hudud "
            "hisoblanadi. Dengizning suv sathi yiliga bir metrdan pasayib boryapti. Suv yuzasi 2012-yil dekabr holatiga "
            "koʻra, dengiz sathidan 427 metr pastda. Oʻlik dengiz sayyoramizdagi eng shoʻr suv havzalaridan biri. "
            "Shoʻrlik darajasi 340-350 promillega yetadi (Oʻrtayer dengizida bu koʻrsatkich 40 pm). Oʻlik dengiz atmosferasida "
            "kislorod boshqa dengizlardagidan oʻn foiz koʻp. Suv tuzga yuqori darajada toʻyingani sababli unda bemalol "
            "chalqancha yotib gazeta oʻqish mumkin.\n\n"
            "III QISM:\n"
            "Suv haddan ortiq shoʻr boʻlganligi sababli tirik mavjudot yashamaydi, Iordan daryosi quyilish joyidagina ayrim "
            "bakteriyalar aniqlangan. XXI asr boshlarida dengizdan yetmishga yaqin zamburugʻsimon mitti mavjudotlar va katta "
            "qalpoqli qoʻziqorinlar topilgan. Dengizga quyiladigan suv oqimi hajmi 1,43 milliard kubometrdan (yiliga) soʻnggi "
            "qirq yil mobaynida 100 million kubometrga oʻzgardi. Oʻlik dengizidagina tuzda sulfatlar kam, bromid koʻp. Bu esa "
            "dengiz suvini shifobaxsh qilgan. Shu sababli dengiz sohilidagi dam olish va davolanish maskanlariga Yer sharining "
            "turli burchaklaridan har yili millionlab sayyohlar, bemorlar keladi. Kurortlar asosan teri, mushak, nafas yoʻli, "
            "asab kasalliklarni davolashga ixtisoslashgan.\n\n"
            "IV QISM:\n"
            "Oʻlik dengiz tubidan minerallarga boy, brom, yod va garmonsimon moddalarga toʻyingan sulfidli balchiq-loy qazib "
            "olinadi (hozirda yerosti boʻshliqlari turarjoylarga xavf solmoqda). Oʻlik dengizning hayratlanarli jihati unda "
            "tabiiy asfalt yuzaga keladi. Bunga sabab boʻluvchi bitum moddasidan misrliklar qadimda moʻmiyolash ishlarida "
            "foydalanganlar. Atmosfera bosimining juda yuqoriligi ham mintaqaning ijobiy xususiyatlaridan. Atmosferada "
            "changlar va allergenlar yoʻq. Sohil juda quyida joylashgani va Yer yuzidagi eng qalin ozon qatlami shu yerda "
            "boʻlgani tufayli quyoshdan ultrabinafsha nurlari kam tushgani bois oftobda bemalol toblanish mumkin."
        )
        passage1 = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            title="O'lik dengiz (Ilmiy matn)",
            content=p1_content,
            order=1,
            source="Ilmiy-ommabop geografik tadqiqotlar majmuasi",
        )

        p2_content = (
            "Aziz Nesin. Ming marta shukur! (hikoya)\n\n"
            "Kadikoʻyda Boʻstonji tomonga qatnaydigan tramvayning oxirgi vagoniga bir amallab chiqib oldim. "
            "Vagonning orqa tomonidagi maydonchada sakkiz kishi tiqilishib ketyapmiz. Oyogʻiga kigiz mahsi bilan kalish, "
            "boshiga yirtiq shapka kiyib olgan bir moʻysafid qoʻlidagi toʻrvani orqa tomondagi oynakka qoʻydi. Shapka kiygan "
            "oʻrta yashar yoʻlovchi ogʻziga somon tiqilgan savatini temir sandiq ustiga qoʻygach, yonidagi odamga murojaat qildi:\n"
            "— Oshnam, ehtiyot boʻling, ichida tuxum bor.\n"
            "Sakkiz yoʻlovchi orasida tuxumdan gap ochilib ketdi. Aslida savatda tuxum oʻrniga mix boʻlganida ham nima toʻgʻrisida "
            "boʻlmasin, baribir gap boʻlardi. Chunki odam odamni koʻrganda yigʻilib qolgan gaplarini aytib ichini boʻshatgisi keladi.\n"
            "— Tuxum qanchadan boʻldi? — deb soʻradi yirtiq shapka kiygan boyagi moʻysafid.\n"
            "— E, soʻramang, tuxumning narxi chaqib olaman deydi.\n"
            "— Hozir narxi osmonga chiqmagan narsa qoldimi, hammasi shunaqa…\n"
            "Charm kamzul kiygan, qop-qora moʻylovli odam bilan ikkovimizgina gapga aralashmadik. Qolgan olti kishi fotihaga qoʻl "
            "ochib, omin deyayotganday baravariga «toʻgʻri» deb yubordi.\n"
            "— Hozir arzon narsa qoldimi oʻzi?\n"
            "— Arzonchilikni tushda koʻramiz, afandim, tushda.\n"
            "— Shu ketishimiz boʻlsa, oxiri nima boʻlarkin-a?!\n"
            "— Ishqilib, oxiri baxayr boʻlsin-da!\n"
            "— Shu ketishimiz boʻlsa, oxiri baxayr boʻlishiga koʻzim yetmay qoldi.\n"
            "— Kecha narxi ikki lira turgan narsa bugun ikki yarim liraga chiqib ketadi-ya. Axir, bu nima degan gap? "
            "Sen uyda uxlab yotganingda ular kechasi bilan narxlarni oshirib chiqishadimi, nima balo.\n"
            "— Qimmatlikka qimmat-a… Lekin bozorda molning oʻzi yoʻq-da, ogʻayni.\n"
            "Olti yoʻlovchi shu tarzda biri olib-biri qoʻyib gapirar, biri gapirayotganda boshqalari «shunday», «toʻgʻri, juda toʻgʻri», "
            "«rost gap» deb tasdiqlab turishardi.\n"
            "Tramvay Oltiyoʻlga kelib toʻxtadi. Tushadigan odam boʻlmadi. Bizning maydonchaga yana bir yoʻlovchi chiqdi.\n"
            "— Tirikchilik juda ogʻir boʻlib qoldi, — dedi tuxumlarning egasi, — ilgarilari naq ajdahoning ogʻzidan ovqat olardik. "
            "Endi oʻsha ajdar ogʻzidagi ovqat ham naq ichiga kirib ketdi. Qani, mard boʻlsang ogʻziga qoʻlingni tiqib koʻr-chi.\n"
            "Yangi chiqqan yoʻlovchi gapga aralashdi:\n"
            "— Qimmatchilik tinkani quritgani yetmaganday, ijara haqi sillani quritib tashladi.\n"
            "Yana hammasi baravar «toʻgʻri» deb yuborishdi. Shu koʻyi biri qimmatchilikdan, boshqasi ijara haqi balandligidan, "
            "yana biri kerakli narsani topib boʻlmasligidan, boshqasi uy-joydan gapirib jigʻibiyron boʻlardi. Toʻgʻrisini aytsam, "
            "men oʻsha yerda eshitgan gaplarimni hozir yozishga ham botinolmayman. Ular shu darajada qizishib ketishgan ediki, "
            "koʻrgan kishi bularni ishdan chiqib, horigan-charchagan holda uylariga emas, xuddi norozilik bildirish uchun biror "
            "mitingga ketishyapti, deb oʻylashi mumkin edi. Ularning ovozlari balandlashib, aytayotgan gaplari chinakam nutqqa aylanib ketardi.\n"
            "Ularga qarab: [1] «Hoy, vatandoshlar, bunaqa qilmang, gaplaringiz to‘g‘ri-ku, lekin siz aytgandek unchalik emas. "
            "Qolaversa, bunaqa joyda past-baland gaplarni aytaversangiz, boshingiz baloga qolishi mumkin» demoqchi bo‘ldim-u, lekin "
            "yuragim betlamay indayolmadim. Jahli chiqib turgan odamning yoniga yoʻlab boʻladimi! Sizni u bir balo qilib qoʻyishi ham "
            "mumkin. Ularning fikriga qoʻshilmaganimdan keyin indamay ketaversam nima qiladi?\n"
            "Tramvay Yoʻgʻirtchi bekatidan jilishi bilan ular yana avjga chiqib ketishdi. Menga oʻxshab boyadan beri jim kelayotgan charm "
            "kamzulli odam chidab turolmay:\n"
            "Gapni gapirgan u boʻldi-yu, men qoʻrqib ketdim. Oʻrtada janjal chiqib, yetti kishi bir boʻlib charm poʻstinlini bemalol "
            "dabdala qilib tashlashi mumkin. Yetti yoʻlovchiga sekin razm soldim. Ular ham charm poʻstinliga tikilib turishibdi. "
            "Oʻrtaga jimlik choʻkdi. Goʻyo ular bu odam nima deganini, maqsadi nima ekanligini tushunmaganday.\n"
            "— Nima boʻlsa yoʻq deysizlar. Nima yoʻq ekan? Ming marta shukur, qidirsa hamma narsa topiladi.\n"
            "Yetti yoʻlovchi hayratda. Yuzini ajin bosgan xomush yoʻlovchi birinchi boʻlib oʻziga keldi:\n"
            "— Ming marta shukur! — deb yuborishdi.\n"
            "— Toʻgʻri. U narsa yoʻq, bu narsa yoʻq, deyaverib, borini ham quritdik. Oʻrtamizdan baraka koʻtarildi. Ming marta shukur, "
            "hamma narsa serob.\n"
            "— Yoʻqchilikka ham, borchilikka ham oʻzimiz aybdormiz. Bittasi turib «choy yoʻq» deydigan boʻlsa, hamma choyga yopishadi. "
            "Qarabsizki, choy topib boʻlmay qoladi. Shunday qilgandan keyin, bor narsa ham yoʻqoladi-da. Ming qatla shukur, hamma narsa bor.\n"
            "— Xudoga shukur, hamma yoqda toʻkinchilik.\n"
            "Tramvay Feneryoʻliga kelib toʻxtagan edi, yoʻlovchilardan biri:\n"
            "— Ming marta shukur, ming marta shukur, — deganicha vagondan tushib ketdi.\n"
            "— Koʻrinib turibdi, hozir sanoatimizda koʻtarilish bor, — yana gap boshladi charm kamzulli, — shuning uchun chetga mol "
            "chiqaryapmiz-u, oʻzimiz-mol olmayapmiz. Ba’zi narsalar topilmayotganligining sababi ham shunda.\n"
            "«Ming marta shukur»ga oʻrganib qolganlardan biri:\n"
            "— Topilmayapti, ming marta shukur, — deb yubordi.\n"
            "U shu zahotiyoq xatosini tuzatdi:\n"
            "— Ha, hozir koʻtarilish payti-da, nari borsa bir-ikkita narsa topilmaydi, xolos. Payti kelib ular ham topilib qolar, "
            "ming marta shukur.\n"
            "Yana charm kamzulli gapga tushdi:\n"
            "— Ming marta shukur, Istambul shu vaqtga qadar bunchalik koʻtarilishni, bunchalik farovonlikni koʻrmagan.\n"
            "— Toʻgʻri aytasiz, hecham koʻrmagan, ming marta shukur. Ya’ni hozir koʻryapti. Sulton Fotih zamonidan buyon qoʻl "
            "urilmagan koʻchalar ochilyapti.\n"
            "— Ha, ochilyapti, ming marta shukur.\n"
            "— Ba’zi narsalarni buzib tashlashyapti.\n"
            "— Buzib tashlashyapti, ming… Hah, yoʻllar ochishyapti.\n"
            "«Ming marta shukur»ni ming marta eshitib, Jaddai boʻstonga yetib keldik. Maydonchada ketayotgan yoʻlovchilar birin-ketib "
            "tushib, bu yogʻiga charm kamzulli odam bilan ikkovimiz qoldik. U toʻsatdan:\n"
            "— Siz nima deysiz? Boyadan beri ogʻiz ochganingiz yoʻq! — deb yuborsa boʻladimi.\n"
            "Manavi rasvogarchilikni qarang, nima qilaman endi? Boshimni egib, yelkamni uchirdim-da, ikki qoʻlimni ikki tomonga yoydim. "
            "Bu «nima deyishga hayronman» deganim edi. Men na boyagi gaplarga qoʻshiladigan pessimist, na «ming marta shukur» deydigan "
            "optimist edim. Charm kamzulli yana qoʻymadi:\n"
            "— Xoʻsh, siz nima deysiz?\n"
            "Tramvay bunchalik tez ketmayotgan boʻlganida, oʻlay agar, vagondan sakrab tushib qolardim. Noilojman, charm kamzulli esa "
            "savolini yana qaytardi. Men ham yana yelka uchirib, bilmayman, deganday labimni burdim.\n"
            "— Shunaqa pastkash odamlar ham bor-a? — deb soʻradi mendan.\n"
            "— Kimni aytyapsiz? — dedim hayron boʻlib.\n"
            "— Hozirgina ming marta shukur deb valdirab kelganlarni-da.\n"
            "— Ha…\n"
            "— Hozir hammasi meni soʻkyapti. «Ming marta shukur» deb turganlaridayoq buni sezgan edim. Bularni qayoqqa sudrasang, "
            "oʻsha yoqqa ketaverishadi. Faqat sudrashni bilsang boʻldi.\n"
            "Tramvay Erankoʻyga yaqinlashib qoldi.\n"
            "— Nima deysiz, qimmatchiligi rostmi oʻzi?\n"
            "Charm kamzulli mendan qanday javob kutayotganligini bilmaganligim uchun mushkul ahvolda qoldim.\n"
            "— Chindan ham qidirgan narsa topilmaydimi? Chindan ham qimmatchilikmi?\n"
            "— Ming marta shukur! — dedim men ham.\n"
            "Shu payt tramvay toʻxtagan edi, bir sakrab yerga tushdim. Charm kamzullidan qutulganimga chindan ham ming marta shukur!"
        )
        passage2 = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            title="Aziz Nesin. Ming marta shukur! (Badiiy hikoya)",
            content=p2_content,
            order=2,
            source="Aziz Nesin, satirik hikoyalar to'plami",
        )

        p3_content = (
            "Alisher Navoiy. G‘azal\n\n"
            "1. Ishq aro vasling tilab, hajringda bo‘ldum dardnok,\n"
            "   Xasta yanglig‘kim, hayot ummididin bo‘lg‘ay halok.\n\n"
            "2. Yo‘q ajab, gar ul quyosh navhangg‘a boqmas, ey ko‘ngul,\n"
            "   O‘tqa ne g‘am garchi kuygan nola aylar dardnok.\n\n"
            "3. Tekkanin yetkach, ochar paykoni ko‘ksum chokining,\n"
            "   Ul kalid o‘lmish, ajal darvozasi go‘yo bu chok.\n\n"
            "4. Aylar erduk pok ishq o‘tig‘a kuymak orzu,\n"
            "   Shukrilillah, oqibat kuydurdi ishqing bizni pok.\n\n"
            "5. Soldi may ul hur shavqin ko‘ngluma, ey bog‘bon,\n"
            "   Berding o‘xshar parvarish kavsar ziloli birla tok.\n\n"
            "6. Ishq aro do‘zaxdin, ey nosih, meni qo‘rqutmakim,\n"
            "   Hajr o‘tin ko‘rgan samandarg‘a sharardin qayda bok.\n\n"
            "7. To taning avji hayot ustidadur, sen xok bo‘l,\n"
            "   Istasangkim avj tutqaysen taning bo‘lg‘anda xok.\n\n"
            "8. Ey Navoiy, shomi g‘amdin ayru yo‘qtur subhi vasl,\n"
            "   Oq erur, lekin qorartur har neni rang etsa zok.\n\n"
            "LUG‘AT:\n"
            "Navha – nola, yig‘i\n"
            "Nosih – nasihatgo‘y\n"
            "Paykon – kamon o‘qidagi uchli temir, tikanning o‘tkir uchi\n"
            "Pok – 1) pok, toza, sof; 2) butunlay, tamoman, butkul\n"
            "Kavsar – jannat bulog‘i\n"
            "Samandar – olov ichida yashovchi afsonaviy jonivor\n"
            "Bok – qo‘rquv, xavf, vahm\n"
            "Sharar – uchqun, yolqin\n"
            "Subh – tong\n"
            "Zok – charm qoraytirish uchun ishlatiladigan bo‘yoq"
        )
        passage3 = ReadingPassage.objects.create(
            test=test,
            section=sec_lit,
            title="Alisher Navoiy — Ishq aro vasling tilab, hajringda bo‘ldum dardnok (G'azal)",
            content=p3_content,
            order=3,
            source="Alisher Navoiy, g'azallar devoni",
        )

        # 7. Questions Spec (1..45)
        questions_spec: list[dict[str, Any]] = [
            # 1 (1c)
            {
                "pos": 1,
                "section": sec_lang,
                "text": "Imloviy jihatdan to‘g‘ri yozilgan so‘zlar qatorini aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. 'poyandoz', 'pachaqlamoq', 'landavur' so'zlari amaldagi imlo qoidalariga "
                    "muvofiq to'liq to'g'ri yozilgan. Boshqa variantlarda: A) masxaraboz (xato: mazxaraboz); "
                    "B) kristall, monopoliya (xato: kristal, manopoliya); D) tadqiqot (xato: tatqiqot)."
                ),
                "choices": [
                    ("A) mazxaraboz, ibratomuz, tanovvul", False),
                    ("B) deklaratsiya, kristal, manopoliya", False),
                    ("C) poyandoz, pachaqlamoq, landavur", True),
                    ("D) to‘g‘anoq, mutanosib, tatqiqot", False),
                ],
            },
            # 2 (2c)
            {
                "pos": 2,
                "section": sec_lang,
                "text": "Qaysi javobda imloviy jihatdan xato yozilgan nom berilgan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. 'Milliy Xavfsizlik Xizmati' birikmasida vazirlik va davlat idoralari nomlarining "
                    "faqat birinchi so'zi bosh harf bilan yozilishi lozim: 'Milliy xavfsizlik xizmati'."
                ),
                "choices": [
                    ("A) Yurt ravnaqidagi xizmatlari uchun beriladigan “O‘zbekiston Qahramoni” unvoni 1994-yil 5-mayda ta’sis etilgan.", False),
                    ("B) “El-yurt hurmati” ordeni harbiy mahorati, ilm-fan, adabiyot va san’atdagi xizmatlari uchun beriladi.", False),
                    ("C) “Jasorat” medali bilan harbiy xizmatchilar, Milliy Xavfsizlik Xizmati va Ichki ishlar vazirligi xodimlari mukofotlanadilar.", True),
                    ("D) “O‘zbekiston Qahramoni” unvoni bilan taqdirlangan shaxsga “Oltin Yulduz” medali topshiriladi.", False),
                ],
            },
            # 3 (3c)
            {
                "pos": 3,
                "section": sec_lang,
                "text": "Qaysi javobda so‘zning muqobili xato ko‘rsatilgan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. 'budjet' so'zining o'zbekcha muqobili 'pul' emas, balki davlat daromadlari va "
                    "xarajatlari rejasi / mablag' smetasidir."
                ),
                "choices": [
                    ("A) xeshteg — kalitso‘z", False),
                    ("B) probel — bo‘shliq", False),
                    ("C) budjet — pul", True),
                    ("D) status — maqom", False),
                ],
            },
            # 4 (4b)
            {
                "pos": 4,
                "section": sec_lang,
                "text": "Nutqda o‘zaro ma’nodoshlik hosil qila oladigan so‘zlar berilgan javobni belgilang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. 'bo'sh', 'xom', 'puch' so'zlari 'bo'sh gap', 'xom xayol', 'puch da'vo' birikmalarida "
                    "o'zaro ma'nodoshlik hosil qiladi."
                ),
                "choices": [
                    ("A) badal, hisob, evaz", False),
                    ("B) bo‘sh, xom, puch", True),
                    ("C) ziynat, suluv, hasham", False),
                    ("D) qochoq, daydi, bezori", False),
                ],
            },
            # 5 (5d)
            {
                "pos": 5,
                "section": sec_lang,
                "text": "Qaysi javobda qo‘shimcha qo‘llash bilan bog‘liq uslubiy xatolik mavjud?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. 'sementli zinasida' birikmasida materialni bildiruvchi so'zga -li sifat yasovchi "
                    "qo'shimchasi noo'rin qo'shilgan, 'sement zinasida' bo'lishi lozim edi."
                ),
                "choices": [
                    ("A) Hay-hay, bu qanday noinsofgarchilik! Urmang! – deb o‘rtaga tushdi Vali aka.", False),
                    ("B) Top-toza kafelli yo‘lakdan o‘tib, bo‘limga kirdik.", False),
                    ("C) Navro‘zi olam – tabiatning beta’rif yashashi, demak, umrlarning boshlanishi ham.", False),
                    ("D) Yigitlar xarob stansiyaning sementli zinasida non kavshab o‘tirishgan ekan.", True),
                ],
            },
            # 6 (6b)
            {
                "pos": 6,
                "section": sec_lang,
                "text": "Qaysi javobda so‘z qo‘llash bilan bog‘liq uslubiy xatolik kuzatilgan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Rassom surat chizadi va ranglarda 'tasvirlaydi'. 'Tavsiflash' esa xususiyatini "
                    "so'zda bayon qilishdir, shuning uchun 'ranglarda tavsiflashga urinaman' ifodasi so'z qo'llashdagi xatolikdir."
                ),
                "choices": [
                    ("A) Odamlarda tafakkur kuchi ortgani sari ulardagi tasavvur kuchi ham ortib bormoqda.", False),
                    ("B) Kamina suratlarimda bu kabi gulzorlarni turfa xil nafis ranglarda tavsiflashga urinaman.", True),
                    ("C) Otabek bilan Kumushning ishqiy sarguzashtlari, fojiasi mahorat bilan hikoya qilingan.", False),
                    ("D) Millatimiz faxri – ona tilimizni ardoqlashimiz, unga muhabbatli bo‘lishimiz lozim.", False),
                ],
            },
            # 7 (7b)
            {
                "pos": 7,
                "section": sec_lang,
                "text": (
                    "Quyidagi gapda qatnashgan qo‘shimchalar haqida berilgan xato fikrlar sonini toping.\n\n"
                    "\"Bahor kelishi bilan tabiatda o‘zgarishlar seziladi, daraxtlar yashnab, qushlar yana gapirishga – "
                    "sayrashga tushadi, osmon esa yorqin nurlari bilan yer yuziga iliqlik baxsh etib, mavsumiy yangilanishni boshlab beradi.\"\n\n"
                    "1) Ot yasovchi qo‘shimcha bilan shakldosh bo‘la oladigan sifat yasovchi qo‘shimcha qatnashgan.\n"
                    "2) Asos+so‘z yasovchi+lug‘aviy shakl yasovchi+lug‘aviy shakl yasovchi qolipidagi so‘z mavjud.\n"
                    "3) Lug‘aviy shakl yasovchi bilan omonim bo‘la oladigan fe’l yasovchi qo‘shimcha ikki o‘rinda qatnashgan.\n"
                    "4) Ko‘makchi bilan ma’nodoshlik hosil qiladigan sintaktik shakl yasovchilar qatnashgan.\n"
                    "5) Sintaktik shakl yasovchi qo‘shimcha bilan shakldosh bo‘la oladigan so‘z yasovchi qo‘shimcha qatnashgan."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B (ikkitasi xato). Berilgan 5 ta hukmdan aynan 2 tasi xato hisoblanadi."
                ),
                "choices": [
                    ("A) bittasi", False),
                    ("B) ikkitasi", True),
                    ("C) to‘rttasi", False),
                    ("D) uchtasi", False),
                ],
            },
            # 8 (8b)
            {
                "pos": 8,
                "section": sec_lang,
                "text": (
                    "Berilgan har uchala gapda ishtirok etgan fe’l shakllarini aniqlang.\n\n"
                    "I. Tabibga ko‘rsatmay kasal tomirin,\n"
                    "   Tuzalmoq hayoli xomdur, hushyor bo‘l.\n"
                    "II. Buyursa uyingga do‘stlaring tashrif,\n"
                    "    Turmagil, ey nodon, xuddiki alif.\n"
                    "III. Dushmaning tomonga otaman deb o‘q,\n"
                    "     O‘zing nishon bo’lib yurmagil endi.\n\n"
                    "1) o‘timli fe’l; 2) qo‘shma fe’l; 3) ko‘makchi fe’l;\n"
                    "4) III shaxsdagi fe’l; 5) buyruq maylidagi fe’l; 6) ravishdosh"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B (faqat 2, 5). Har uchala gapda ham qo'shma fe'l (hushyor bo'l, tashrif buyurmoq, nishon bo'lib) "
                    "va buyruq maylidagi fe'l (hushyor bo'l, turmagil, yurmagil) qatnashgan."
                ),
                "choices": [
                    ("A) 2, 5, 6", False),
                    ("B) faqat 2, 5", True),
                    ("C) 1, 3, 4", False),
                    ("D) 1, 2, 5", False),
                ],
            },
            # 9 (9a)
            {
                "pos": 9,
                "section": sec_lang,
                "text": (
                    "Quyidagi parchada qatnashgan sifatlar haqida berilgan to‘g‘ri hukmlar sonini toping.\n\n"
                    "\"Kech kirib, ajib bir so‘lim payt boshlandi. Sershovqin ko‘chalar orqada qoldi. Bu taraflarda mashinalar "
                    "ko‘p qatnamaganidan chang-to‘zon bo‘lmas, tez-tez yomg‘ir quyib turganidan daraxtlarning shundog‘am "
                    "beg‘ubor barglari yuvilib, xandonpista mag‘zidek och yashil tusda ko‘rinar edi.\"\n\n"
                    "1) Sifatning uch xil ma’no turi qatnashgan;\n"
                    "2) Parchada faqat asliy sifatlar qatnashgan;\n"
                    "3) Yasama sifatlar bir xil sintaktik vazifa bajargan;\n"
                    "4) Sifat darajalarining uch turi ishtirok etgan;\n"
                    "5) Tuzilishiga ko‘ra ikki xil turdagi sifatlar qatnashgan;\n"
                    "6) Otga xos turlovchi qo‘shimcha bilan shakldosh bo‘la oladigan sifat yasovchi qo‘shimcha qatnashgan."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A (1 ta to'g'ri hukm). Matndagi sifatlar bo'yicha tahlil qilinganda faqat 1 ta hukm to'g'ri chiqadi."
                ),
                "choices": [
                    ("A) 1", True),
                    ("B) 4", False),
                    ("C) 2", False),
                    ("D) 3", False),
                ],
            },
            # 10 (10a)
            {
                "pos": 10,
                "section": sec_lang,
                "text": (
                    "Quyidagi parcha haqida berilgan noto‘g‘ri ma’lumotni aniqlang.\n\n"
                    "\"Sen do‘st bo‘l, vaqtida fosh et Yagoni,\n"
                    " Ishqda Otellodan bo‘lgin besh battar.\n"
                    " Asrab qolmoq uchun Mo‘min mirzoni\n"
                    " Tutqaz Alisherning qo‘liga xanjar…\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. 'Asrab qolmoq uchun' birikmasi sabab holi emas, balki maqsad holi hisoblanadi "
                    "va u 'tutqaz' fe'l kesimiga tobelangan."
                ),
                "choices": [
                    ("A) Ko‘makchi fe’lli so‘z qo‘shilmasi bilan ifodalangan sabab holi fe’l kesimga tobelangan.", True),
                    ("B) Shaxsi ma’lum gap ishtirok etgan.", False),
                    ("C) Kesimga bevosita va bilvosita bog‘langan vositasiz to‘ldiruvchi qatnashgan.", False),
                    ("D) Faqat tobe bo‘lak vazifasida kelgan aniqlovchi qatnashgan.", False),
                ],
            },
            # 11 (11b)
            {
                "pos": 11,
                "section": sec_lang,
                "text": (
                    "Gapdagi so‘zlarning mazmun va grammatik jihatdan bog‘lanishi to‘g‘ri ko‘rsatilgan javobni toping.\n\n"
                    "\"Davlatning iqtisodiy mustaqilligi yangi bosqichga olib chiqilishi, bozor munosabatlarining sog‘lom "
                    "shakllanishi, milliy mahsulotlar raqobatbardoshligining ortishi va jahon standartlariga javob bera olishi "
                    "tadbirkorlar uchun yaratib berilgan keng ko‘lamli imkoniyatlarning amaliy natijasidir.\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. 'iqtisodiy mustaqillik' (moslashuv/bitishuv) va 'jahon standartlari' birikmalari "
                    "mazmun va grammatik jihatdan to'g'ri bog'langan sintaktik juftlikdir."
                ),
                "choices": [
                    ("A) mahsulotlarning ortishi, shakllanishi natijasidir", False),
                    ("B) iqtisodiy mustaqillik, jahon standartlari", True),
                    ("C) tadbirkorlik uchun imkoniyatlar, javob bera olishi", False),
                    ("D) bozor munosabatlari, keng yaratib berilgan", False),
                ],
            },
            # 12 (12d)
            {
                "pos": 12,
                "section": sec_lang,
                "text": (
                    "Raqamlangan qaysi gap(lar)da tinish belgisi bilan xatolik mavjud?\n\n"
                    "1) Boshqalarning fikri, taklifi, mulohazalari do‘kon rastasida sotish uchun turgan buyumday narsa: "
                    "ularni tosh-taroziga qo‘y, narx-navosini surishtir - chog‘ing kelsa, olasan, yo‘qsa - yo‘q\n"
                    "2) Yaxshiga yaxshi bo‘l, yomonga – yomon.\n"
                    "   Gullarga gul bo‘lgin, tikonga – tikon.\n"
                    "3) Tinch bitar ishga ham, qilaversa jang,\n"
                    "   Demak, ul odamning aqlin bosmish zang."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D (1, 3). 1-gapda defis/tire va vergullar o'rnida hamda oxirida nuqta qo'yilmagan; "
                    "3-gapda esa 'Tinch bitar ishga ham'dan keyin vergul noo'rin qo'yilgan."
                ),
                "choices": [
                    ("A) faqat 3", False),
                    ("B) 1, 2, 3", False),
                    ("C) 1, 2", False),
                    ("D) 1, 3", True),
                ],
            },
            # 13 (13d)
            {
                "pos": 13,
                "section": sec_lit,
                "text": (
                    "Onore de Balzakning “Sagʻri teri tilsimi” romanidan olingan quyidagi parcha mazmuni haqida berilgan toʻgʻri hukmni aniqlang.\n\n"
                    "\"Chol yigitga xanjarni uzatdi, u terining harf bosilgan joyidan kesib koʻrishga urindi. Ammo u terining yupqa "
                    "qavatini kesib olishi bilan oʻrniga yana oʻsha harflar avvalgiday aniq boʻlib qolaverdi, goʻyo ularning yuqori "
                    "qismi kesib olinmaganday edi... Sirli soʻzlarning maʼnosi bu edi: 'Mening egam hamma narsaga ega boʻladi, ammo "
                    "uning joniga men ega boʻlaman. Tangri irodasi shu. Istaganingni tila, ijobat boʻlgʻay. Lekin tilagingni "
                    "hayotingga mosla. Joning – menda. Har bir tilagingdan umring kunlari kamaygani singari men ham kamayaman. "
                    "Menga ega boʻlishni istaysanmi? Ol. Senga tangri yor boʻlgʻay. Omin!'\""
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Parchada insonning cheksiz xohish-istaklari bilan unga berilgan cheklangan umr o'rtasidagi "
                    "falsafiy ziddiyat va to'lov haqida so'z boradi."
                ),
                "choices": [
                    ("A) Tilsimni topgan odam dunyodagi eng baxtli kishiga aylanishi ifoda etilgan.", False),
                    ("B) Yozuvlarda ochkoʻzlik va hasaddan qaytaruvchi diniy pand-nasihat ifodalangan.", False),
                    ("C) Teri oʻz egasini balo-qazolardan asrovchi qudratli tumor ekani taʼkidlangan.", False),
                    ("D) Cheksiz istaklar bilan cheklangan umr oʻrtasidagi ziddiyat ifodalangan.", True),
                ],
            },
            # 14 (14b)
            {
                "pos": 14,
                "section": sec_lit,
                "text": (
                    "Jorj Oruellning “Molxona” asaridagi deyarli barcha hayvonlar yomon koʻradigan obraz haqida berilgan toʻgʻri hukmni aniqlang."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Qarg'a Mouzes hayvonlarga Muz tog'i (Shakarqamish tog'i) haqidagi ertaklarni aytib berar, "
                    "mehnat qilmasdan mish-mishlar tarqatgani uchun hayvonlar uni yoqtirmas edilar."
                ),
                "choices": [
                    ("A) Ushbu hayvon molxonadagi eng aqlli jonivor hisoblanib, yozish va oʻqishni tez oʻzlashtirib oladi.", False),
                    ("B) Bu obraz hayvonlarga turli xil voqealar aytib beradi, bundan tashqari, Muz togʻi haqidagi mish-mishlarning tarqalishiga sababchi boʻladi.", True),
                    ("C) Ushbu asar qahramoni Napaleonning barcha topshiriqlarini chin dildan bajarar edi, hayvonlar orasidagi eng kuchlisi edi, tegirmon qurilishida ham katta hissa qoʻshgan edi.", False),
                    ("D) Bu obraz hayvonlar tomonidan ishlab chiqilgan 7 ta tamoyilni choʻchqalar qilgan amallarga moslab oʻzgartirib oʻqir edi, shuning uchun hamma uni yomon koʻrar edi.", False),
                ],
            },
            # 15 (15c)
            {
                "pos": 15,
                "section": sec_lit,
                "text": (
                    "Abdulla Qahhorning “O‘g‘ri” hikoyasidan olingan parchada ifodalangan mazmunni aniqlang.\n\n"
                    "“– Qidirtirsakmikin-a? – dedi amin chinchalog‘ini etigining ostiga artib. – Suyunchisi nima bo‘ladi?\n"
                    "Suyunchidan chashna olib kelinmadimi?\n"
                    "Aminning bu gapi Qobil boboga “Ma, ho‘kizing”, deganday bo‘lib ketdi.\n"
                    "– Kam bo‘lmang, – dedi pulni uzatib, – yana xizmatingizdaman.\n"
                    "– Men beto‘xtov pristavga xabar beraman. O‘zi chaqirtiradi”."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. Parchada oddiy mehnatkash xalqning kulfatidan foydalanib poraxo'rlik qilayotgan, "
                    "mansab vazifasini shaxsiy manfaati quroliga aylantirgan amaldorlar qiyofasi qoralangan."
                ),
                "choices": [
                    ("A) Insofli va adolatli rahbarlarning xalq uchun jon kuydirishi ifodalangan.", False),
                    ("B) Jamiyatda qallobliklar va o‘g‘riliklar ko‘paygani ifodalangan.", False),
                    ("C) Mansab vazifasidan o‘z manfaati yo‘lida foydalangan amaldor qoralangan.", True),
                    ("D) Millatning xalq dardini xolis eshituvchi asl farzandlari madh etilgan.", False),
                ],
            },
            # 16 (16d)
            {
                "pos": 16,
                "section": sec_lit,
                "text": (
                    "Sharof Boshbekovning “Temir xotin” komediyasidan olingan parchada ifodalangan mazmunni aniqlang.\n\n"
                    "“Progress bor. Ilgari tezak yoqilardi, hozir tezakni solyarka bilan yoqayapmiz. Yaxshi yonayapti. "
                    "To‘g‘ri, ovqatdan sal-pal hidi keladi-yu, lekin o‘rganib ketar ekan odam”."
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Bu achchiq satira orqali ilmiy-texnik taraqqiyot asrida ham qoloqlikdan qutula olmagan, "
                    "haqiqiy taraqqiyot o'rniga soxta 'yangilik' bilan ovunayotgan millat fojiasi ko'rsatilgan."
                ),
                "choices": [
                    ("A) Parchada turmush tarzidan norozi bo‘lgan insonning qarashlari tasvirlangan.", False),
                    ("B) Parchada amalga oshirilayotgan islohotlar xalqning turmush darajasini yaxshilay olmayotgani tasvirlangan.", False),
                    ("C) Parchada yaratilgan qulay sharoitdan foydalana olmayotgan insonlar tasvirlangan.", False),
                    ("D) Parchada ta’lim, ilm-fanda ortda qolayotgan millatning qiyofasi tasvirlangan.", True),
                ],
            },
            # 17 (17a)
            {
                "pos": 17,
                "section": sec_lit,
                "text": (
                    "Erkin Vohidovning dostonidan olingan quyidagi parchada ifodalangan mazmunni aniqlang.\n\n"
                    "“Xayolning tumanli pardasi aro\n"
                    " Yillar ko‘z oldimda charx urayotir.\n"
                    " Qishloq ko‘chasidan zanjiday qaro\n"
                    " Olov bolaligim yugurayotir.\n"
                    " Dunyo qayg‘usiga bo‘lmagan oshno,\n"
                    " Qah-qah urayotir, barq urayotir.\n"
                    " Bilmas, boshi uzra bulutli samo\n"
                    " Chaqmoq chaqayotir, guldurayotir.\n"
                    " Bilmas, yaralangan bu majruh dunyo\n"
                    " Qasos so‘rayotir, bong urayotir...”"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. 'Bulutli samo' ifodasi orqali yaqinlashib kelayotgan urush fojiasi va xalq boshiga "
                    "tushadigan g'am-alamli kunlar ramziy tarzda tasvirlangan."
                ),
                "choices": [
                    ("A) “Bulutli samo” ifodasi orqali xalq boshiga kelayotgan g‘am-tashvishli kunlar nazarda tutilgan.", True),
                    ("B) “Qah-qah urayotir” ifodasi orqali bosqinchilarning zaharxanda kulgisi nazarda tutilgan.", False),
                    ("C) “Zanjiday qaro” ifodasi orqali mamlakat bolalarining zanjirband etilgani nazarda tutilgan.", False),
                    ("D) “Majruh dunyo” ifodasi orqali dushmanga mag‘lub bo‘lgan millat nazarda tutilgan.", False),
                ],
            },
            # 18 (18a - Reading Passage 1)
            {
                "pos": 18,
                "section": sec_reading,
                "passage": passage1,
                "text": "Matnda aks etgan toʻgʻri ma’lumotni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. O'lik dengiz tuzida sulfatlar kam va bromid ko'pligi suvni shifobaxsh qilgan, "
                    "shu sababli bu yerda davolanish va turizm keng rivojlangan."
                ),
                "choices": [
                    ("A) Oʻlik dengizi tuzining minerallar tarkibi boshqa dengizlarnikidan farqli ekanligi bu yerda turizm rivojiga ham taʻsir qilgan.", True),
                    ("B) Atmosfera bosimining juda yuqoriligi bois dengiz sohili atmosferasida allergenlar, boshqa tirik mavjudotlar yashay olmaydi.", False),
                    ("C) Qadimda misrliklar moʻmiyolashda foydalanish uchun Oʻlik dengizidan tabiiy asfalt, yaʻni bitum moddasini olib ketishgan.", False),
                    ("D) Ozon qatlami qalinligi bois quyosh nurlarining kam tushishi natijasida dengiz sohilida oʻsimliklarning kam oʻsishi kuzatiladi.", False),
                ],
            },
            # 19 (19a - Reading Passage 1)
            {
                "pos": 19,
                "section": sec_reading,
                "passage": passage1,
                "text": "Matn mazmuni asosida toʻgʻri shakllantirilgan jumlani aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Matnning 1-qismida suv ostidagi o'rmonzor daraxtlarini intensiv tuzlar qotirib, "
                    "qadimgi o'simliklarni saqlab qolgani bayon etilgan."
                ),
                "choices": [
                    ("A) Intensiv tuzlar tufayli dengiz tubida qolib ketgan qadimgi hayot qoldiqlari saqlanib qolgan.", True),
                    ("B) Ayniqsa dengizning daryolar quyiladigan joylarida suvning shoʻrlik darajasi yuqori boʻladi.", False),
                    ("C) Quyoshdan ultrabinafsha nurlarining kam tushishi dengiz ob-havosiga salbiy taʻsir qiladi.", False),
                    ("D) Tabiiy asfalt qazib olinishining yoʻlga qoʻyilgani sanoat rivoji uchun katta foyda keltiradi.", False),
                ],
            },
            # 20 (20a - Reading Passage 1)
            {
                "pos": 20,
                "section": sec_reading,
                "passage": passage1,
                "text": "Matn mazmunida aks etgan ma’lumotni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Matnning IV qismida loy qazib olinishi natijasida yerosti bo'shliqlari paydo bo'lib, "
                    "turarjoylarga xavf solayotgani aytilgan, demak uni cheklash zarurati mavjud."
                ),
                "choices": [
                    ("A) Oʻlik dengizdan sulfidli balchiq-loy qazib olinishini cheklash lozim.", True),
                    ("B) Oʻlik dengiz Yer yuzidagi baliqlar yashamaydigan yagona dengizdir.", False),
                    ("C) Oʻlik dengizga quyiladigan daryolarning suvlari tez-tez qurib qoladi.", False),
                    ("D) Oʻlik dengizi tarixi insonning tabiatga tajovuzi oqibatini aks ettiradi.", False),
                ],
            },
            # 21 (21d - Reading Passage 1)
            {
                "pos": 21,
                "section": sec_reading,
                "passage": passage1,
                "text": "Matnning raqamlab koʻrsatilgan qaysi qismida uslubiy xatolikni vujudga keltirgan gap mavjud?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D (4-qismda). IV qismda 'sabab bo'luvchi' kabi uslubiy jihatdan g'aliz ifodalar mavjud."
                ),
                "choices": [
                    ("A) 1", False),
                    ("B) 2", False),
                    ("C) 3", False),
                    ("D) 4", True),
                ],
            },
            # 22 (22a - Reading Passage 1)
            {
                "pos": 22,
                "section": sec_reading,
                "passage": passage1,
                "text": "Matn mazmunida aks etgan maʻlumotni aniqlang.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. Matnda Qur'oni karimdagi Lut qavmi voqeasi va Verner Keller arxeologik topilmalari "
                    "o'zaro mos kelishi, ya'ni ilmiy tadqiqotlar diniy qarashlarni ilmiy-nazariy asoslashi aytilgan."
                ),
                "choices": [
                    ("A) Oʻlik dengizi tadqiqotlari diniy qarashlarni ilmiy-nazariy asoslaydi.", True),
                    ("B) Oʻlik dengizi suvining shoʻrlik darajasi yildan yilga ortib bormoqda.", False),
                    ("C) Oʻlik dengiz Yer yuzi koʻllari ichida eng chuqur koʻl hisoblanadi.", False),
                    ("D) Oʻlik dengizi sathi yildan yilga sezilar-sezilmas pasayib bormoqda.", False),
                ],
            },
            # 23 (23c - Reading Passage 2)
            {
                "pos": 23,
                "section": sec_reading,
                "passage": passage2,
                "text": "Hikoya mazmuni haqida berilgan to‘g‘ri fikrni toping.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. Odamlar og'ir hayot va qimmatlikdan charchashgan, lekin haqiqiy kurashish yoki fikr "
                    "aytish o'rniga bitta odam 'shukur' deyishi bilan darhol o'zlarini aldab shukur qilib ketaveradilar."
                ),
                "choices": [
                    ("A) Charm kamzulli odam jamiyatdagi haqiqatni aytadi.", False),
                    ("B) Tramvaydagi yo‘lovchilar har biri mustaqil fikrga ega shaxslardir.", False),
                    ("C) Odamlar qimmatlikdan charchagan, ammo u bilan kurashishga jur’at etolmaydi.", True),
                    ("D) Kuzatuvchi o‘z fikrini dadil himoya qiladi.", False),
                ],
            },
            # 24 (24c - Reading Passage 2)
            {
                "pos": 24,
                "section": sec_reading,
                "passage": passage2,
                "text": "Hikoyaning asosiy g‘oyasi qaysi javobda to‘g‘ri izohlangan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. Aziz Nesin asarida jamiyatdagi soxta shukronalik, befarqlik, ijtimoiy loqaydlik "
                    "va ommaning ko'r-ko'rona itoatkorligi fosh etilgan."
                ),
                "choices": [
                    ("A) Odamlar shukronalikni hech qachon unutmasligi kerak.", False),
                    ("B) Hayotning barcha og‘irliklari sabr bilan yengiladi degan fikrni targ‘ib qiladi.", False),
                    ("C) Jamiyatdagi soxta shukronalik, befarqlik va ijtimoiy loqaydlik tanqid qilinadi.", True),
                    ("D) Shukr qilish insonni ruhiy kuchli qiladi degan g‘oyani beradi.", False),
                ],
            },
            # 25 (25b - Reading Passage 2)
            {
                "pos": 25,
                "section": sec_reading,
                "passage": passage2,
                "text": "Hikoyada [1] raqami bilan ajratib ko‘rsatilgan parcha orqali qanday mazmun ifodalangan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. So'z erkinligi bo'lmagan, erkin fikr taqiqlangan jamiyatda ochiq gapirgan insonning "
                    "boshi baloga qolishi mumkinligi ifodalangan."
                ),
                "choices": [
                    ("A) Jamiyatning o‘ziga yarasha tartib-qoidalari bor, ularga amal qilmoq lozim.", False),
                    ("B) So‘z erkinligi ta’minlanmagan jamiyatda inson hayoti xavf ostida qolishi mumkin.", True),
                    ("C) Hayotda faqat nolib yashash najot sari yetaklamaydi.", False),
                    ("D) Insonning haqiqiy boyligi sog‘lik va tinchligida, qolgani hal bo‘ladigan muammolar.", False),
                ],
            },
            # 26 (26d - Reading Passage 2)
            {
                "pos": 26,
                "section": sec_reading,
                "passage": passage2,
                "text": "Hikoyadagi ramziy obraz va detallar haqida berilgan to‘g‘ri javobni toping.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. Kuzatuvchi (muallif) — haqiqatni bilib, hamma narsani tushunib tursa-da, jim "
                    "o'tirgan, omma bilan ochiq kurashishdan qo'rquvchi ziyolilar qatlamini ifodalaydi."
                ),
                "choices": [
                    ("A) Tramvay – o‘y-xayollari, dunyoqarashi turlicha bo‘lgan odamlar timsoli.", False),
                    ("B) Charm kamzulli odam – jamiyatga adolat o‘rnatmoqchi bo‘lgan xalqparvar ishchi.", False),
                    ("C) Tushayotgan yo‘lovchilar – har narsadan kamchilik qidirib, aybni o‘zidan emas, boshqalardan qidiradigan kishilar timsoli.", False),
                    ("D) Kuzatuvchi (muallif obrazi) – fikrli, ammo jim. Haqiqatni o‘ylaydigan, lekin aytolmaydigan ziyoli qatlam ramzi.", True),
                ],
            },
            # 27 (27c - Reading Passage 2)
            {
                "pos": 27,
                "section": sec_reading,
                "passage": passage2,
                "text": "Asarda “ming marta shukur” so‘zining takrorlanishi qanday ramziy ma’noga ega?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. Bu takror muammoni hal qilish o'rniga adolatsizlikni ko'r-ko'rona, befarqlik bilan "
                    "qabul qilish va haqiqatdan qochishni fosh etuvchi badiiy vositadir."
                ),
                "choices": [
                    ("A) Qahramonlarning Allohga bo‘lgan chuqur imonini bildiradi.", False),
                    ("B) Og‘irliklarga sabr qilishni o‘rgatuvchi milliy qadriyatni ko‘rsatadi.", False),
                    ("C) Hayotdagi adolatsizlikni befarqlik bilan qabul qilishni fosh etadi.", True),
                    ("D) Jamiyatda minnatdorlik tuyg‘usining ustuvorligini targ‘ib qiladi.", False),
                ],
            },
            # 28 (28d - Reading Passage 3)
            {
                "pos": 28,
                "section": sec_lit,
                "passage": passage3,
                "text": "G‘azalning matla’si haqida berilgan to‘g‘ri hukmni toping.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. 'Ishq aro vasling tilab, hajringda bo'ldum dardnok' misrasi orqali oshiq visolga "
                    "yetishishni tilab, hijron dardi chekayotgani bayon qilingan."
                ),
                "choices": [
                    ("A) Oshiqning holati yashashdan umidini uzgan bemorga qiyoslangan.", False),
                    ("B) Ma’shuqa bergan ozorlar sabab oshiq yashashdan umid uzib kasalga chalingan.", False),
                    ("C) Oshiqlik hijron dardiga duchor bo‘lgan kasalga o‘xshaydi.", False),
                    ("D) Visolga yetishni xohlagan oshiq hijron sababli dardga chalingan.", True),
                ],
            },
            # 29 (29c - Reading Passage 3)
            {
                "pos": 29,
                "section": sec_lit,
                "passage": passage3,
                "text": "G‘azalda quyidagi o‘xshatishlardan qay biri uchramaydi?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — C. G'azalda tokning parvarishi kavsar ziloliga qiyoslangan, biroq mayning o'zi bevosita "
                    "kavsar suviga o'xshatib sifatlanmagan."
                ),
                "choices": [
                    ("A) Oshiq ko‘ksidagi chok ajal darvozasiga o‘xshatilgan.", False),
                    ("B) Yor quyoshga qiyoslangan.", False),
                    ("C) May kavsar suviga o‘xshatilgan.", True),
                    ("D) Oshiq samandarga qiyoslangan.", False),
                ],
            },
            # 30 (30d - Reading Passage 3)
            {
                "pos": 30,
                "section": sec_lit,
                "passage": passage3,
                "text": "G‘azaldagi baytlar mazmuni haqida berilgan xato hukmni toping.",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. 2-baytda 'O'tqa ne g'am garchi kuygan nola aylar dardnok' deyiladi, ya'ni olovga uning "
                    "ichida kuyayotgan odamning nolasi parvo emas (ma'shuqa oshiqning faryodiga beparvo)."
                ),
                "choices": [
                    ("A) Pok muhabbat o‘tida yonishni orzu qilgan oshiq oqibatda shu ishq sabab butkul yonib kuyadi.", False),
                    ("B) Hijron olovini ko‘rgan oshiqqa do‘zax olovi xuddi uchqundek bo‘lib tuyuladi.", False),
                    ("C) Ishq mayi oshiqning ko‘ngliga ul hurning shavqini soldi.", False),
                    ("D) Olovda kuygan odam qancha dod-faryod qilsa ham, qolganlar unga parvo qilmaydi.", True),
                ],
            },
            # 31 (31d - Reading Passage 3)
            {
                "pos": 31,
                "section": sec_lit,
                "passage": passage3,
                "text": "Yettinchi bayt mazmuni qaysi javobda to‘g‘ri izohlangan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. 'To taning avji hayot ustidadur, sen xok bo'l, Istasangkim avj tutqaysen taning bo'lg'anda xok' "
                    "— jisming tuproqqa kirganda yuksak maqom topishni istasang, tiriklik paytingda tuproq kabi kamtar bo'l."
                ),
                "choices": [
                    ("A) Toki hayot ekansan, yorga yetishish uchun doim uning oyog‘i ostida tuproqdek bo‘l.", False),
                    ("B) Taning tuproqqa aylanmasin desang, tiriklik paytingda yuqori maqomga erishish uchun tuproqdek oyoqosti bo‘lma.", False),
                    ("C) Tiriklikning eng avj pallasida qanchalik buyuk maqomga erishgan bo‘lsang ham, kun kelib jisming oddiy tuproqqa qorishib ketadi.", False),
                    ("D) Jisming tuproqqa topshirilgandan keyin ham yuqori maqomga erishmoqchi bo‘lsang, jisming hayot bo‘lib turganda tuproq kabi xokisor bo‘l.", True),
                ],
            },
            # 32 (32b - Reading Passage 3)
            {
                "pos": 32,
                "section": sec_lit,
                "passage": passage3,
                "text": "G‘azalning maqta’sida qaysi badiiy san’atlardan foydalanilgan?",
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — B. Maqta'da 'oq' va 'qorartur' so'zlari orqali tazod (antiteza) hamda ikkinchi misrada "
                    "hayotiy dalil keltirish orqali tamsil (masal keltirish) san'ati qo'llangan."
                ),
                "choices": [
                    ("A) tashbeh va iyhom", False),
                    ("B) tazod va tamsil", True),
                    ("C) husni ta’lil va tashxis", False),
                    ("D) tajnis va tazod", False),
                ],
            },
            # 33 (Matching 33 -> A)
            {
                "pos": 33,
                "section": sec_lang,
                "text": (
                    "Gaplar (33, 34, 35) va sintaktik tahlilga oid izohlar (A–F) ni o'zaro to'g'ri moslashtiring:\n\n"
                    "33-gap: \"Matnni yozuvda qayd etish (aks ettirish) yozma nutqning muhim sifatlaridan hisoblanadi, "
                    "unga og‘zaki nutqqa nisbatan muayyan afzallik baxsh etadi.\"\n\n"
                    "Ushbu gap uchun mos keluvchi sintaktik izohni tanlang:"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — A. '(aks ettirish)' qavs ichida berilib, 'qayd etish' so'zining ma'nosini "
                    "aniqlashtiruvchi ajratilgan izohlovchi bo'lak vazifasida kelgan."
                ),
                "choices": [
                    ("A) ajratilgan bo‘lak", True),
                    ("B) kiritma qatnashgan gap", False),
                    ("C) atov gap", False),
                    ("D) egasi noma’lum gap", False),
                    ("E) undalmali gap", False),
                    ("F) so‘z-gap", False),
                ],
            },
            # 34 (Matching 34 -> D)
            {
                "pos": 34,
                "section": sec_lang,
                "text": (
                    "Gaplar (33, 34, 35) va sintaktik tahlilga oid izohlar (A–F) ni o'zaro to'g'ri moslashtiring:\n\n"
                    "34-gap: \"Ba’zi nashrlaming mualliflarini bir-biridan farq qiluvchi tavsiyalar berishdan, "
                    "haddan tashqari so‘zamolikka berilib ketishmasdan, nutqqa o‘rinli-o‘rinsiz ilmoqli so‘roqlarni kiritishdan "
                    "ogohlantirish kerak.\"\n\n"
                    "Ushbu gap uchun mos keluvchi sintaktik izohni tanlang:"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — D. 'ogohlantirish kerak' modal so'zli birikmasi bilan ifodalangan, egasi grammatik jihatdan "
                    "mavjud bo'lmagan egasi noma'lum bir tarkibli gap."
                ),
                "choices": [
                    ("A) ajratilgan bo‘lak", False),
                    ("B) kiritma qatnashgan gap", False),
                    ("C) atov gap", False),
                    ("D) egasi noma’lum gap", True),
                    ("E) undalmali gap", False),
                    ("F) so‘z-gap", False),
                ],
            },
            # 35 (Matching 35 -> E)
            {
                "pos": 35,
                "section": sec_lang,
                "text": (
                    "Gaplar (33, 34, 35) va sintaktik tahlilga oid izohlar (A–F) ni o'zaro to'g'ri moslashtiring:\n\n"
                    "35-gap: \"Ona zamin! Qancha-qancha fotihlar-u jahongirlarni, qancha-qancha shoir-u olimlarni "
                    "bag‘ringda allalagan muqaddas beshiksan.\"\n\n"
                    "Ushbu gap uchun mos keluvchi sintaktik izohni tanlang:"
                ),
                "type": Question.QuestionType.SINGLE_CHOICE,
                "points": 2,
                "explanation": (
                    "To'g'ri javob — E. 'Ona zamin!' so'zlovchining murojaatini bildiruvchi undalma bo'lib kelgan."
                ),
                "choices": [
                    ("A) ajratilgan bo‘lak", False),
                    ("B) kiritma qatnashgan gap", False),
                    ("C) atov gap", False),
                    ("D) egasi noma’lum gap", False),
                    ("E) undalmali gap", True),
                    ("F) so‘z-gap", False),
                ],
            },
            # 36
            {
                "pos": 36,
                "section": sec_lang,
                "text": (
                    "Quyida berilgan lug‘aviy ma’nolarni o‘zida ifodalay oladigan shakldoshlik xususiyatiga ega bo‘lgan iborani yozing:\n\n"
                    "Ahdini saqlamoq <———— ? ————> Qaysarlik qilmoq"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "so'zida turmoq | so’zida turmoq | sozida turmoq | so'zida turish | so’zida turish | So'zida turmoq",
                "explanation": (
                    "To'g'ri javob: 'So'zida turmoq'. Ushbu ibora omonim (shakldosh) bo'lib, bir o'rinda bergan va'dasiga "
                    "vafodor bo'lish (ahdini saqlamoq), ikkinchi o'rinda esa o'z aytganidan qaytmaslik (qaysarlik qilmoq) ma'nosini anglatadi."
                ),
            },
            # 37
            {
                "pos": 37,
                "section": sec_lang,
                "text": (
                    "Quyidagi gapda xato qo‘llangan tinish belgisini toping va uning o‘rniga qo‘llanishi lozim bo‘lgan to‘g‘ri "
                    "tinish belgisini yozing (Format: [Xato tinish belgi] [To'g'ri tinish belgi]):\n\n"
                    "“Hikmatlar xazinasi” asarida: “Inson ikki xil tarbiya oladi – birinchi tarbiya hayotdagi ilk ustozi – "
                    "ota-onasidan olinadi, ikkinchisini unga hayotning o‘zi o‘rgatadi”, – deyiladi."
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "Tire ikki nuqta | tire, ikki nuqta | tire ikki nuqta | - : | - -> : | tire - ikki nuqta | tire : | - ikki nuqta",
                "explanation": (
                    "To'g'ri javob: 'Tire ikki nuqta' (yoki '- :'). Ko'chirma gap ichidagi umumlashtiruvchi so'zdan ('ikki xil tarbiya oladi') "
                    "so'ng tire emas, ikki nuqta qo'yilishi kerak edi."
                ),
            },
            # 38
            {
                "pos": 38,
                "section": sec_lang,
                "text": (
                    "Qo‘shimcha qo‘llash bilan bog‘liq uslubiy xatolik mavjud bo‘lgan so‘zni aniqlang va xatoni bartaraf etgan "
                    "holatda yozing:\n\n"
                    "\"Asarda ruhiy olami orqali kechagi kunini unutmagan, bobolarning amal qilgan yuksak udumlar asosida "
                    "yashagan chin inson haqidagi ma’lumotlar aks etgan.\""
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "Bobolar | bobolar | bobolari | bobolar amal qilgan | bobolarning -> bobolar",
                "explanation": (
                    "To'g'ri javob: 'Bobolar'. 'Bobolarning amal qilgan' birikmasida -ning qaratqich kelishigi ortiqcha va xato "
                    "qo'llangan, chunki sifatdosh bilan bog'langanda 'bobolar amal qilgan udumlar' bo'lishi lozim."
                ),
            },
            # 39
            {
                "pos": 39,
                "section": sec_lang,
                "text": (
                    "Berilgan gapda tinish belgisi bilan ajratilishi lozim bo‘lgan sintaktik birlikni toping va shu birlikni "
                    "vujudga keltirgan so‘zlarni yozing:\n\n"
                    "\"Qorong‘ida Santyago cholning ismi shunday tong yaqinlashayotganini sezdi, eshkak urarkan, qulog‘iga titroq "
                    "tovush chalindi – ucharbaliqlar suvdan chiqar va temirdek qanotlari bilan havoni kesib allaqayoqlarga g‘oyib bo‘lardi.\""
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": "Cholning ismi shunday | cholning ismi shunday | cholning ismi shunday, | kiritma gap",
                "explanation": (
                    "To'g'ri javob: 'Cholning ismi shunday'. Bu birlik gap mazmuniga qo'shimcha izoh kirituvchi kiritma gap bo'lib, "
                    "tinish belgilari (vergul yoki qavs) bilan ajratilishi shart edi."
                ),
            },
            # 40 (Two-part)
            {
                "pos": 40,
                "section": sec_lang,
                "text": (
                    "Gapdagi soʻzlarning mazmun va grammatik jihatdan bog'lanishini tahlil qiling:\n\n"
                    "\"Yashil iqtisodiyotni rivojlantirish va atrof-muhitni tozaligi haqida gap ketar ekan, avvalo, shuni ta`kidlab o‘tish joizki, "
                    "tabiatni muhofaza qilish, ekologik barqarorlikni ta’minlash va kelajak avlodga sog‘lom muhit qoldirish faqat "
                    "mutasaddilarning emas, har birimizning bugungi kundagi mas’uliyatimizdir.\"\n\n"
                    "Javobni quyidagi 2 ta maydonga yozing:\n"
                    "a) ajratib koʻrsatilgan so‘z ('har birimizning') qaysi so‘zga tobelanib bog‘langan?\n"
                    "b) ajratib koʻrsatilgan so‘z ('ta’minlash') qaysi soʻz(lar) bilan teng bogʻlangan?"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": (
                    "a) mas'uliyatimizdir b) muhofaza qilish, qoldirish | "
                    "a) mas’uliyatimizdir b) muhofaza qilish, qoldirish | "
                    "a) mas'uliyatimizdir b) muhofaza qilish va qoldirish | "
                    "mas'uliyatimizdir, muhofaza qilish, qoldirish | "
                    "mas’uliyatimizdir, muhofaza qilish, qoldirish | "
                    "mas'uliyatimizdir; muhofaza qilish, qoldirish | "
                    "a) mas'uliyatimizdir b) muhofaza qilish qoldirish"
                ),
                "explanation": (
                    "a) 'har birimizning' qaratqich aniqlovchisi 'mas'uliyatimizdir' ot-kesimiga tobelanib bog'langan;\n"
                    "b) 'ta'minlash' harakat nomi 'muhofaza qilish' va 'qoldirish' uyushiq bo'laklari bilan teng bog'langan."
                ),
            },
            # 41 (Two-part)
            {
                "pos": 41,
                "section": sec_lang,
                "text": (
                    "Parchadagi yordamchi so‘zlarning grammatik vazifasini tahlil qiling:\n\n"
                    "\"Yaqinda bo‘lib o‘tgan “Milliy kuylar” musobaqasi tufayli xalqimizning unutilib ketayotgan qadimiy ohanglari "
                    "qayta jonlandi, milliy musiqa tariximizga nazar tashlandi, bu esa tomoshabinlar va san’atga endi qadam qo‘yayotgan "
                    "yoshlar qalbida milliylik ruhini shakllantirishga xizmat qildi.\"\n\n"
                    "Javobni quyidagi 2 ta maydonga yozing:\n"
                    "a) parchadagi qaysi yordamchi so‘z bir gap bo‘lagini boshqasiga tobelantirib bog‘lash uchun xizmat qilgan?\n"
                    "b) parchadagi qaysi vosita bir sodda gapni boshqasiga teng bog‘lash uchun xizmat qilgan?"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": (
                    "a) tufayli b) esa | "
                    "tufayli, esa | "
                    "tufayli; esa | "
                    "tufayli esa | "
                    "a) tufayli ko'makchisi b) esa yuklamasi"
                ),
                "explanation": (
                    "a) 'tufayli' ko'makchisi 'musobaqasi' so'zini 'jonlandi' kesimiga sabab holi qilib tobelantirib bog'lagan;\n"
                    "b) 'esa' vositasi (yuklamasi) zidlov munosabatini bildirib, sodda gaplarni o'zaro teng bog'lagan."
                ),
            },
            # 42 (Two-part)
            {
                "pos": 42,
                "section": sec_lit,
                "text": (
                    "She’riy parchani tahlil qiling va savollarga javob yozing:\n\n"
                    "\"Chun yuzin sevdi ko‘ngul zulf-u zanaxdonin tilar,\n"
                    " Ore Yusufni sevganlar band-u zindon orzular.\"\n\n"
                    "Javobni quyidagi 2 ta maydonga yozing:\n"
                    "a) parchada yorning sochi nimaga qiyoslangan?\n"
                    "b) yorning iyagidagi chuqurcha (zanaxdon) nimaga qiyos etilgan?"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": (
                    "a) band yoki arqon b) zindon | "
                    "a) band b) zindon | "
                    "a) arqon b) zindon | "
                    "band, zindon | "
                    "arqon, zindon | "
                    "band yoki arqon, zindon | "
                    "a) bandga b) zindonga"
                ),
                "explanation": (
                    "a) Yorning jingalak sochi (zulf) oshiqni bog'lovchi kishan, arqon va bog'liqqa (band) qiyoslangan;\n"
                    "b) Yorning iyagidagi chuqurcha (zanaxdon) Yusuf tushgan zindonga (chohga) qiyos etilgan."
                ),
            },
            # 43 (Two-part)
            {
                "pos": 43,
                "section": sec_lit,
                "text": (
                    "She’riy parchaning qofiyasini tahlil qiling va savollarga javob yozing:\n\n"
                    "\"Kirding tushuma subhidam, alminnatu lilloh,\n"
                    " To’le yana qildi karam, alminnatu lilloh.\n"
                    " Hayoti azal husn to‘nin titgali sizga,\n"
                    " O‘lturmas anga gardi g‘am, alminnatu lilloh.\"\n\n"
                    "Javobni quyidagi 2 ta maydonga yozing:\n"
                    "a) qofiyadosh so‘zlardagi raviyni yozing;\n"
                    "b) qofiyaning qaysi turi shakllantirilgan?"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": (
                    "a) m b) muqayyad | "
                    "m, muqayyad | "
                    "m; muqayyad | "
                    "a) m harfi b) muqayyad | "
                    "a) m tovushi b) muqayyad | "
                    "a) m b) muqayyada"
                ),
                "explanation": (
                    "Qofiyadosh so'zlar: 'subhidam', 'karam', 'g‘am'. Radif: 'alminnatu lilloh'.\n"
                    "a) So'z oxiridagi asosiy undosh tovush — ravishdosh undosh 'm' harfi raviy hisoblanadi;\n"
                    "b) Raviy undosh bilan tugab, uning ketidan vasl unlisi kelmagani uchun qofiya turi: 'muqayyad' (bog'langan qofiya)."
                ),
            },
            # 44 (Two-part)
            {
                "pos": 44,
                "section": sec_lit,
                "text": (
                    "She’riy parchani tahlil qiling va savollarga javob yozing:\n\n"
                    "\"Ne toli’durki, har kimni desam yor,\n"
                    " Manga ul oqibat bo‘lur badandesh.\n"
                    " Biravdur gar ani desam ko‘zumsen,\n"
                    " Chekar mujgon kebi qasdimg‘a yuz nish.\"\n\n"
                    "Javobni quyidagi 2 ta maydonga yozing:\n"
                    "a) ushbu parcha qaysi janr namunasi hisoblanadi?\n"
                    "b) she’rdagi qaysi badiiy timsol jafokor do‘st tushunchasini ifodalagan?"
                ),
                "type": Question.QuestionType.TEXT_MATCH,
                "points": 2,
                "correct_text": (
                    "a) qit'a b) ko'z | "
                    "a) qit’a b) ko‘z | "
                    "qit'a, ko'z | "
                    "qit’a, ko‘z | "
                    "a) qita b) koz | "
                    "a) qit'a b) ko'zumsen | "
                    "a) qit’a b) ko‘zumsen"
                ),
                "explanation": (
                    "a) Ushbu falsafiy-axloqiy to'rtlik — qit'a janri namunasidir (faqat juft misralari 'badandesh' va 'nish' qofiyalangan);\n"
                    "b) Shoir o'ziga yaqin bilgan, 'ko'zimdek azizsan' deb e'zozlagan qadrdonining oxir-oqibat kiprikdek nish urib dushmanga aylanishini "
                    "'ko'z' (ko'zumsen) timsoli orqali ifodalagan."
                ),
            },
            # 45 (Written / Essay)
            {
                "pos": 45,
                "section": sec_writing,
                "text": (
                    "ESSE TOPSHIRIG'I (BMBA Milliy Sertifikat 12 mezonli rasmiy formati):\n\n"
                    "Mavzu: Bugungi kunda nafaqaga chiqish yoshi borasida jamiyat vakillari turlicha fikrga ega:\n"
                    "➢ ayrimlar yosh chegarasini qisqartirish kadrlar salohiyati uchun muhimligini ta’kidlashadi;\n"
                    "➢ ayrimlar pensiya yoshining uzaytirilishi yaxshi hayot kafolati ekanligini uqtirishadi.\n"
                    "Nima deb o'ylaysiz, nafaqa yoshining qisqartirilishi kadrlar salohiyatini oshiradimi?\n\n"
                    "Qo'yiladigan rasmiy talablar:\n"
                    "1. Fikr-mulohazalaringizni publitsistik uslubda, mantiqiy izchillikda va adabiy til me’yorlariga amal qilgan holda bayon qiling.\n"
                    "2. Esse uch tarkibiy qismdan iborat bo’lishi lozim:\n"
                    "   I. Kirish: 2-3 jumladan iborat bo'lsin, berilgan vaziyat matnini aynan ko'chirmang;\n"
                    "   II. Asosiy qism: kamida uchta xatboshidan iborat bo'lsin, har bir xatboshida tomonlarning va shaxsiy qarashlaringizni hayotiy misollar va dalillar bilan yoriting;\n"
                    "   III. Xulosa: asosiy qismdagi fikrlarni umumlashtiruvchi 2-3 jumla bo'lsin.\n"
                    "3. Reja tuzilmaydi, epigraf qo'yilmaydi.\n"
                    "4. Minimal hajm: 150 so'z (tavsiya etiladi: 200–350 so'z)."
                ),
                "type": Question.QuestionType.WRITTEN,
                "points": 25,
                "config": {
                    "min_words": 150,
                    "max_words": 500,
                    "rubric": "bmb_12_mezon",
                    "national_cert_scale": True,
                },
                "explanation": (
                    "Esse BMBA rasmiy 12 ta mezoni bo'yicha baholanadi:\n"
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
            title="Nafaqa yoshining qisqartirilishi kadrlar salohiyatini oshiradimi? (Umid Shukurov Mock)",
            defaults={
                "description": (
                    "Bugungi kunda nafaqaga chiqish yoshi borasida jamiyat vakillari turlicha fikrga ega: "
                    "ayrimlar yosh chegarasini qisqartirish kadrlar salohiyati uchun muhimligini ta’kidlashadi; "
                    "ayrimlar pensiya yoshining uzaytirilishi yaxshi hayot kafolati ekanligini uqtirishadi. "
                    "Nima deb o'ylaysiz, nafaqa yoshining qisqartirilishi kadrlar salohiyatini oshiradimi? "
                    "Fikr-mulohazalaringizni publitsistik uslubda 12 mezon asosida bayon qiling."
                ),
                "category": EssayTopic.Category.ONA_TILI,
                "word_limit_min": 150,
                "word_limit_max": 500,
                "time_limit_minutes": 60,
                "national_cert_scale": True,
                "sample_outline": (
                    "I. Kirish: Zamonaviy mehnat bozorida pensiya yoshi va mehnat unumdorligi o'rtasidagi munosabat.\n"
                    "II. Asosiy qism:\n"
                    "  - 1-qarash: Yosh kadrlarga yo'l ochish, innovatsiya va zamonaviy texnologiyalarni joriy etish afzalliklari.\n"
                    "  - 2-qarash: Tajribali, yetuk mutaxassislarning kasbiy mahorati va ustoz-shogirdlik an'analarining o'rni.\n"
                    "  - Shaxsiy mulohaza va hayotiy misol: Har ikkala avlod salohiyatini uyg'unlashtirish imkoniyatlari.\n"
                    "III. Xulosa: Moslashuvchan va oqilona pensiya islohotlari orqali kadrlar salohiyatini barqaror yuksaltirish."
                ),
            },
        )
        if not topic_created and not essay_topic.national_cert_scale:
            essay_topic.national_cert_scale = True
            essay_topic.save(update_fields=["national_cert_scale"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded BMBA Shukurov Mock Test!\n"
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
