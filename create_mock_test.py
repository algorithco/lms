"""
Create Mock Test 29-yanvar: Ona tili va adabiyoti milliy sertifikat testi
44 ta savol: 35 ta MCQ + 9 ta yozma
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.tests.models import Test, Question, Choice
from apps.courses.models import Course
from django.contrib.auth import get_user_model

User = get_user_model()


def create_test():
    # Get or create course with a teacher
    teacher = User.objects.filter(role="teacher").first()
    if not teacher:
        teacher = User.objects.filter(role="admin").first()
    if not teacher:
        teacher = User.objects.first()
    
    course, _ = Course.objects.get_or_create(
        title="Ona tili va adabiyoti",
        defaults={"description": "Milliy sertifikatga tayyorgarlik", "teacher": teacher}
    )

    # Create test
    test, created = Test.objects.get_or_create(
        title="Mock Test 29-yanvar — Ona tili va adabiyoti",
        defaults={
            "course": course,
            "description": "⚡️Ona tili va adabiyoti fanidan milliy sertifikat testi namunasi.\n\n35 ta tanlov (MCQ) + 9 ta yozma savol.\nJami: 3 soat.",
            "time_limit_minutes": 180,  # 3 hours
            "pass_percentage": 60,
            "difficulty": "hard",
            "is_active": True,
        }
    )
    if not created:
        # Delete old questions if re-creating
        test.questions.all().delete()
        print(f"Re-creating questions for existing test: {test.title}")
    else:
        print(f"Created test: {test.title}")

    # ========== MCQ QUESTIONS (1-35) ==========
    mcq_data = [
        # (question_text, choices_list, correct_letter, points)
        # 1
        ("Insoniy jihatdan to'g'ri yozilgan so'zlar qatorini aniqlang.",
         ["A) tasnif, muxojatama, tabiiy", "B) ixtiro, tasvif, tasdiqlash", "C) muruvvat, tasnif, tabiiy", "D) maishiy, tadbir, tafakkur"],
         "D", 1.1),
        # 2
        ("Insoniy jihatdan to'g'ri yozilgan so'zini aniqlang.",
         ["A) o'z-o'zidan, vov-vov, bost-nabadat", "B) o'z-o'zidan, vo-volamoq, hod-hovli", "C) o'z-o'zida, vo-vorga, bost-hovli", "D) o'z-o'zigcha, voyvoyak, tajribiy-hol"],
         "C", 1.1),
        # 3
        ("Qaysi gapda ochiq so'zi o'z ma'nosida qo'llangan?",
         ["A) Nodirning o'z fikrlarini jahlilik oldida ham ochiq aytishiga kuchi yetmadi.",
          "B) Yigitning qizg'anish arzchasiga munosmilar o'zini ochibdi.",
          "C) Bahorning dushanba kuni ochiq eshiklaridan biri qulflanmadi.",
          "D) Inson ota-oning dastidan boshini ochirib, o'g'lini chaqirdi."],
         "D", 1.1),
        # 4
        ("O'zaro ma'nodoshlik holatini qila oladigan so'zlarni aniqlang.",
         ["A) hurmat — ehtirom — hurmat", "B) bayon — hikoya — voqea",
          "C) hikoya — voqea — bayon", "D) voqea — bayon — hikoya"],
         "C", 1.7),
        # 5
        ("Quyidagi gaplarda qizil so'zi ma'nosida ishlatilganligini aniqlang.",
         ["A) Ishonib ishdoqning qizilini bersa, Arslonning qizilini olar.",
          "B) Sizlarning nazoratingiz va yurishib qo'yilgandir.",
          "C) Quyidagilarning nima sababdan bilmasliklari hamma narsada muommoga aylanib qolgan.",
          "D) Mana shuning uchun ham bizda xalqning milliy hissi, ongida shakllanib qolgan."],
         "D", 1.1),
        # 6
        ("Qaysi gapda g'urur so'zi o'z ma'nosida qo'llangan?",
         ["A) Gapimni eshitishni, g'ururimni sindirishni istamasdim.",
          "B) Deydi — O'zbek xalqining jasoratli va zakovatli kuchini ko'rsatish uchun.",
          "C) G'alaba, yurtingizga yengilib to'la chin ishonch va orziqib o'tirgan edi.",
          "D) Uning yigiti g'ururini yengib, o'zini yo'qotib borardi."],
         "A", 1.1),
        # 7
        ("Qaysi gapda negativ o'zida ixtibor-teskari ma'nodagi, bug'aviy shakl yasovchi va sintaktik shakl yasovchi qo'shimcha qo'llaniladi?",
         ["A) Vatan ravnaqi... yuridika xizmat qil... deb o'ylardi.",
          "B) Ta'lim tiz... uring har doim bo'g'... i o'zaro hamjihatlik bilan ishla... i kerak.",
          "C) Boshqalarning manfaatiga ishla... p bo'lsin, ular kuchida mador... beriladi.",
          "D) Shahda sifat ko'rsat... larining sifat beran... qo'g'ish o'zgarishlardan da'vat ber..."],
         "D", 1.7),
        # 8
        ("Har urinish parchasini mustahkam egan fe'l shaklini aniqlang.\nI. Yuragim qon bo'ldi, ko'zlarim qimirlashib sholdi dim,\nUstmoni, kamoni kosib kelib qolmasin.\nII. Shirin so'zdan aslging qo'shim o'zing,\nYomon so'zdan asl qomon odamdan So'zlap,\nYomonni so'zdan yomonligin g'amgin.\nIII. Shirin so'zni o'zga qo'sham emasdiplash,\nO'zga yurtga yomon bo'lmaydi g'amgin.",
         ["1) buyruq majhulti; 2) rap'sima fe'l; 3) shaklanish fe'li; 4) o'zlik qo'shimchasi;",
          "B) 3 va 4", "C) 2 va 6", "D) 5 va 6"],
         "D", 2.5),
        # 9
        ("Qaysi gapda iddikot egan qadimda qanday maqsadni munosabatni ifodalagan?",
         ["A) qizuvchi ma'nosini", "B) fikr mavzusini ma'nosini",
          "C) sabab ma'nosini", "D) natija ma'nosini"],
         "B", 1.7),
        # 10
        ("Berilgan gapdagi to'g'ri fe'lni aniqlang.\nXizmat oxirigi yetib kelganida, qodimiy, nazorati va qodimgurlarning osoyishtalikda yashashlari uchun yaxshi sharoitlarni ruxda tashkil etishgan.",
         ["A) rivojlanishi to'g'risidan to'g'ri to'g'ri to'g'risida to'g'ri to'g'ri",
          "B) Peyt holini fe'l kencing to'g'risidan to'g'ri to'g'ri",
          "C) Maqsad holini vazifasini to'g'risidan to'g'ri to'g'ri",
          "D) Tuzilishini aniqlashga kelishiga kelishida yordam berishda to'g'ri"],
         "A", 1.7),
        # 11
        ("Qo'shmadagi tuzilishini aniqlang.\nBu yerda Sharq, jihatdan bog'lanishi to'g'ri ko'rsatilgan javobni aniqlang.",
         ["A) qodimiy gr'izl divier", "B) qodimiy va go'zal, bugun sir emas",
          "C) boshqalardan ekansligi, najotat Sharq", "D) bining Sharq, keng janobliklik"],
         "B", 1.7),
        # 12
        ("Qaysi gaplarda tire o'zaro bir xil punktuatsion qoida asosida qo'llangan?",
         ["A) 2 va 3", "B) 1 va 2", "C) 5 va 6", "D) 2 va 4"],
         "D", 2.5),
        # 13
        ("She'riy parchadagi to'g'ri qo'llimni aniqlang.\nMening yo' qo'llimda risolfada arzonlik qildim\nO'zim yo g'uncha zarramonadur hol",
         ["A) Mutlaq va munosabat qofiya qilingan", "B) I stondaki rivoj vazifasini bajargan",
          "C) Yozuv va sig'ir tadbif qofiya qilingan", "D) o' xil rivoj vazifasini bajargan"],
         "A", 1.7),
        # 14
        ("She'riy parchadagi to'g'ri qo'llimni aniqlang.\nLangarida ohir tushubdi, qo'g'irchaq, suyurlar, sular ani suyi o'sgan ko'zgak",
         ["A) El so'rga tashbeh qilingan", "B) Sor tashxissi asosida tavsiflangan",
          "C) Husni tali sun'at sifat egatgan", "D) Tarixi sun'at sifat sifat egatgan"],
         "C", 1.7),
        # 15
        ("Oq oqir hikoyasining asosiy qaysi qahramonlari javobda to'g'ri tanlangan?",
         ["A) Yurt og'ishini, Vatanga muhabbat belgisi sifatida",
          "B) Qadr-dostlari, dirtilik va sadoqat og'ishgan",
          "C) Ilova-illatiga, o'zlikni anglashga da'vat etilgan",
          "D) Erk va osoylik ichida kiribsa da'vat etilgan"],
         "B", 1.7),
        # 16
        ("Kecha va kunda romandagi qaysi tarixiy voqea qaysiga olib kelgan?",
         ["A) millat styollarining qatag'on qilinishi",
          "B) birinchi jahon urushi voqealari",
          "C) turkiy xalqlarning qo'shilishi voqealari",
          "D) mustamlakilikka qarshi kurashlar voqealari"],
         "A", 1.7),
        # 17
        ("Ikki eshik orasi romanidagi XATO ishlangan javobni aniqlang.",
         ["A) Ikkinchi jahon urushini, front va front orti voqealari tasvirlangan",
          "B) Turkiston alohida qo'shilib solgan zilzila kinoyatlar",
          "C) Mustaqillikning dastlabki yillardagi voqealari qalamga olingan",
          "D) Oddiy qishloq o'quvchisining qatag'on qilinishi haqida o'z bahsi"],
         "C", 1.7),
        # 18
        ("Qaysi gapda birikma ma'nosida qo'llangan so'z to'g'ri aniqlangan?",
         ["A) tomchi (suv tomchisi)", "B) qora (qora rang)", "C) qizil (qizil rang)", "D) oq (oq rang)"],
         "A", 1.1),
        # 19
        ("Quyidagi so'zlardan qaysi biri noto'g'ri yozilgan?",
         ["A) mustaqillik", "B) bag'rikenglik", "C) mezbonlik", "D) hamjihatlik"],
         "C", 1.1),
        # 20
        ("Qaysi gapda qo'shma fe'l ishlatilgan?",
         ["A) Bolalar o'ynab-kulishdi", "B) U yurib-keldi", "C) U o'qib-yozdi", "D) Biz mehnat qildik"],
         "B", 1.1),
        # 21
        ("Qaysi so'zning ma'nosi to'g'ri berilgan?",
         ["A) Mehr — muhabbat, ipoteka", "B) Sabr — chidamlilik, jahldorlik",
          "C) Dono — bilimdon, ahmoq", "D) Alim — olim, johil"],
         "A", 1.1),
        # 22
        ("Qaysi gapda xorijiy so'z qo'llanmagan?",
         ["A) biznes", "B) muvaffaqiyat", "C) marketing", "D) konferensiya"],
         "B", 1.1),
        # 23
        ("Qaysi gapda ot-sifat birikmasi ishlatilgan?",
         ["A) Oltin sochli qiz", "B) O'qish kerak", "C) Kitob o'qidim", "D) U keladi"],
         "A", 1.1),
        # 24
        ("Qaysi gapda fe'l shakli to'g'ri?",
         ["A) U kitob o'qidi", "B) U kitob o'qigan", "C) U kitob o'qiydi", "D) U kitob o'qir edi"],
         "B", 1.1),
        # 25
        ("Qaysi gapda otlar to'g'ri qo'llanilgan?",
         ["A) U o'qituvchi", "B) U o'qituvchida", "C) U o'qituvchidan", "D) U o'qituvchiga"],
         "C", 1.1),
        # 26
        ("Qaysi gapda sifat to'g'ri ishlatilgan?",
         ["A) U juda yaxshi", "B) U juda yaxshilik", "C) U juda yaxshilikda", "D) U juda yaxshilikdan"],
         "A", 1.1),
        # 27
        ("Qaysi so'zda prefiks to'g'ri ajratilgan?",
         ["A) be-patra", "B) no-munosabat", "C) ersiz-erk", "D) mas'uliyat"],
         "A", 1.1),
        # 28
        ("Qaysi gapda ravish to'g'ri qo'llanilgan?",
         ["A) U tez yugurdi", "B) U tezlikda yugurdi", "C) U tezlikdan yugurdi", "D) U tezlikka yugurdi"],
         "B", 1.1),
        # 29
        ("Qaysi gapda kelishik to'g'ri ishlatilgan?",
         ["A) Men do'stim bilan ketdim", "B) Men do'stimda o'qidim", "C) Men do'stimga yozdim", "D) Men do'stimdan oldim"],
         "D", 1.1),
        # 30
        ("Qaysi gapda son to'g'ri qo'llanilgan?",
         ["A) Ikki kitob oldim", "B) Ikkita kitob oldim", "C) Ikki kitoblardan oldim", "D) Ikkita kitoblardan oldim"],
         "B", 1.1),
        # 31
        ("Qaysi gapda olmosh to'g'ri ishlatilgan?",
         ["A) Bu mening kitobim", "B) Bu mening kitobimmi", "C) Shu mening kitobim", "D) U mening kitobim"],
         "B", 1.1),
        # 32
        ("Qaysi gapda birikma to'g'ri?",
         ["A) Mehnat qilmoq", "B) Mehnat borasida", "C) Mehnatdan keyin", "D) Mehnatga kirishmoq"],
         "A", 1.1),
        # 33
        ("Qaysi gapda fe'l turkumi to'g'ri aniqlangan?",
         ["A) U o'qiydi — o'tgan zamon", "B) U o'qiydi — hozirgi zamon",
          "C) U o'qiydi — kelajak zamon", "D) U o'qiydi — buyruq"],
         "B", 1.1),
        # 34
        ("Qaysi gapda noto'g'ri yozilgan?",
         ["A) Mustaqillik", "B) Erkinlik", "C) Baxtiyorlik", "D) Baxillik"],
         "D", 1.1),
        # 35
        ("Qaysi gapda to'g'ri qo'llanilgan?",
         ["A) Uning maqsadi — o'qish", "B) Uning maqsadini — o'qish",
          "C) Uning maqsadida — o'qish", "D) Uning maqsadidan — o'qish"],
         "A", 1.1),
    ]

    for i, (q_text, choices, correct, points) in enumerate(mcq_data, 1):
        question = Question.objects.create(
            test=test,
            text=q_text,
            position=i,
            points=points,
        )
        for choice_text in choices:
            letter = choice_text[0]  # A, B, C, D
            Choice.objects.create(
                question=question,
                text=choice_text[3:],  # Remove "A) " prefix
                is_correct=(letter == correct),
            )
        print(f"  Q{i}: {correct} ({points} ball)")

    # ========== WRITTEN QUESTIONS (36-44) ==========
    written_data = [
        # (question_text, correct_answer, points)
        (36, "Quyidagi jumlada birikma ma'nosida qo'llangan so'zni toping.\n\"Yaqin do'stlari bilan uchrashdi.\"\nJavob: _________", "yaqin", 2.0),
        (37, "Quyidagi jumlada punctuatsion belgilarni to'ldiring.\n\"Ona tilimiz — boylik, _________(,).\" \nJavob: _________", ";(,).", 2.0),
        (38, "Quyidagi jumlada otning qaysi turkumini aniqlang.\n\"O'rttirma nisbat oshdi.\"\nJavob: _________", "orttirma nisbat", 2.0),
        (39, "Quyidagi jumlada gap qismini aniqlang.\n\"U tez yugurdi.\"\n\"Tez\" so'zi qaysi gap qismi? Javob: _________", "hol", 2.0),
        (40, "Quyidagi jumlada to'g'ri javobni belgilang.\n\"U _________ qadrini biladigan, kurasha oladigan inson edi.\"\na) insonni  b) qadrini biladigan, kurasha oladigan\nJavob: _________", "insonni", 2.0),
        (41, "Quyidagi gap tuzilishini aniqlang.\n\"U keldi, chunki dars boshlandi.\"\nBu qanday gap? Javob: _________\na) chunki  b) bergashgan qo'shma gap", "chunki", 2.0),
        (42, "Quyidagi jumlada badiiy ifodani aniqlang.\n\"Uning yuragi tosh kabi so'ndi.\"\nBu qanday badiiy ifoda? Javob: _________\na) tashbeh  b) talmeh", "tashbeh", 2.0),
        (43, "Quyidagi so'zda qo'shimcha turini aniqlang.\n\"O'zbekistonlik\" so'zidagi qo'shimcha.\nJavob: _________\na) \"sh\"  b) mutlaq", "\"sh\"", 2.0),
        (44, "Quyidagi qarama-qarshilikni aniqlang.\n\"Baxillik va saxiylik\" — bu qanday munosabat? Javob: _________\na) baxillik  b) saxiylik", "baxillik", 2.0),
    ]

    for num, q_text, correct_answer, points in written_data:
        question = Question.objects.create(
            test=test,
            text=q_text,
            position=num,
            points=points,
        )
        # For written questions, create a single "correct answer" choice
        Choice.objects.create(
            question=question,
            text=f"To'g'ri javob: {correct_answer}",
            is_correct=True,
        )
        print(f"  Q{num}: Yozma — {correct_answer} ({points} ball)")

    total_questions = Question.objects.filter(test=test).count()
    total_points = sum(q.points for q in test.questions.all())
    print(f"\n✅ Test yaratildi!")
    print(f"   {total_questions} ta savol")
    print(f"   {total_points} jami ball")
    print(f"   {test.time_limit_minutes} daqiqa vaqt")


if __name__ == "__main__":
    create_test()
