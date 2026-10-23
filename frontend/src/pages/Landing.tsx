import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Mic, Headphones, Play, Pause } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';
import { School, landingFor, formatDisplayName } from '../lib/api';
import TrendChart, { type TrendPoint } from '../components/TrendChart';
import HowItWorks from '../components/HowItWorks';
import SEO from '../components/SEO';
import LanguageSwitcher from '../components/LanguageSwitcher';
import UserNavDropdown from '../components/UserNavDropdown';
import confetti from 'canvas-confetti';
import {
  BotIcon,
  CheckIcon,
  FileTextIcon,
  LightbulbIcon,
  MenuIcon,
  MoonIcon,
  PenLineIcon,
  SunIcon,
  SwordsIcon,
  TrophyIcon,
  XIcon,
} from '../components/icons';

// ---------------------------------------------------------------------------
// TYPES & DATA DEFINITIONS
// ---------------------------------------------------------------------------
export type MainSubject = 'uzbek' | 'english';
export type ExamTrack = 'ielts' | 'multilevel' | 'national_certificate' | 'attestation';

// 12 BMB Milliy Sertifikat Essay Assessment Criteria (Uzbek Track)
interface CriterionData {
  id: number;
  name: string;
  score: string;
  max: number;
  percent: number;
  desc: string;
  advice: string;
  category: 'content' | 'grammar' | 'style';
}

const ESSAY_12_CRITERIA: CriterionData[] = [
  {
    id: 1,
    name: "Mavzuni to'g'ri va to'liq tushunish",
    score: '5.0 / 5',
    max: 5,
    percent: 100,
    desc: "Mavzu mohiyati chuqur tahlil qilingan, asosiy g'oyadan chetga chiqilmagan.",
    advice: "A'lo daraja! Muallif konsepsiyasi va mavzuning dolzarbligi mukammal yoritilgan.",
    category: 'content',
  },
  {
    id: 2,
    name: 'Fikriy izchillik va mantiqiy reja',
    score: '5.0 / 5',
    max: 5,
    percent: 100,
    desc: "Kirish, asosiy qism va xulosa o'rtasidagi mantiqiy aloqadorlik benuqson.",
    advice: "Har bir xatboshi alohida mikromavzuni ochib beradi va umumiy g'oyaga xizmat qiladi.",
    category: 'content',
  },
  {
    id: 3,
    name: 'Mustaqil mulohaza va dalillar',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: 'Shaxsiy tahlil mustahkam, biroq tarixiy qiyos biroz kuchaytirilishi mumkin.',
    advice: "Zamonaviy hayotiy misollar va adabiy paralellardan foydalanish tavsiya etiladi.",
    category: 'content',
  },
  {
    id: 4,
    name: 'Badiiy asar matniga tayanish',
    score: '5.0 / 5',
    max: 5,
    percent: 100,
    desc: "Alisher Navoiy 'Xamsa'sidan olingan baytlar o'rinli keltirilgan va tahlil qilingan.",
    advice: "Matndan olingan iqtiboslar qahramon ruhiyatini ochib berishda to'liq qo'llangan.",
    category: 'content',
  },
  {
    id: 5,
    name: "Adabiyotshunoslik atamalarining o'rinliligi",
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: "Tazod, istiora, tashxis kabi badiiy san'atlar to'g'ri qo'llangan.",
    advice: "Yana bir nechta mumtoz poetika atamalarini integratsiya qilish tavsiya etiladi.",
    category: 'style',
  },
  {
    id: 6,
    name: "Lug'at boyligi va obrazlilik",
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: "Fikrni ifodalashda serqirra va jarangdor so'zlar qo'llangan, takrorlar kam.",
    advice: "Sinonimik qatorlardan unumli foydalanilgan, ifoda kuchi yuqori.",
    category: 'style',
  },
  {
    id: 7,
    name: 'Uslubiy ravonlik va ifoda aniqligi',
    score: '5.0 / 5',
    max: 5,
    percent: 100,
    desc: "Uslubiy g'alizliklar yo'q, jumlalar silliq va o'qilishi oson.",
    advice: "Badiiy-publitsistik uslub me'yorlariga to'liq rioya qilingan.",
    category: 'style',
  },
  {
    id: 8,
    name: "Xulosa va umumlashtirish salmog'i",
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: "Xulosa asosiy g'oyani umumlashtiradi, yakuniy ta'sirchan chaqiriq mavjud.",
    advice: "Xulosa qismida shaxsiy ijtimoiy pozitsiya yanada aniq ko'rsatilsa maqsadga muvofiq.",
    category: 'content',
  },
  {
    id: 9,
    name: 'Imlo qoidalariga rioya etilishi',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: "1 ta juz'iy imlo xatosi aniqlandi (tutruq/tuturuq).",
    advice: "Lotin alifbosi orfografik qoidalariga e'tibor qarating.",
    category: 'grammar',
  },
  {
    id: 10,
    name: "Tinish belgilarining to'g'ri qo'llanishi",
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: "Murakkab qo'shma gaplarda vergul va tire qo'llash qoidalariga mos.",
    advice: "Kirish so'zlar atrofidagi vergullarga e'tibor bering.",
    category: 'grammar',
  },
  {
    id: 11,
    name: 'Grammatik qoidalar va gap qurilishi',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: "Kelishik va egalik qo'shimchalari to'g'ri biriktirilgan.",
    advice: "Ega va kesim moslashuvida muvozanat saqlangan.",
    category: 'grammar',
  },
  {
    id: 12,
    name: "Matn kompozitsiyasi va hajm me'yori",
    score: '3.0 / 5',
    max: 5,
    percent: 60,
    desc: "Matn hajmi 320 so'z (standart me'yor: 350-400 so'z).",
    advice: "Hajmni yana 30-40 so'zga kengaytirib, yakuniy qismni to'ldirish tavsiya etiladi.",
    category: 'content',
  },
];

// IELTS 4 Official Assessment Criteria
interface IeltsCriterionData {
  id: number;
  name: string;
  code: string;
  score: string;
  band: number;
  desc: string;
  feedback: string;
  highlights: string[];
}

const IELTS_4_CRITERIA: IeltsCriterionData[] = [
  {
    id: 1,
    name: 'Task Response',
    code: 'TR',
    score: '7.5 / 9.0',
    band: 7.5,
    desc: 'Addresses all parts of the prompt with clear, well-supported arguments and relevant examples.',
    feedback: 'Clear position presented throughout; fully developed stance on AI automation impacts.',
    highlights: ['unprecedented shift', 'cognitive automation', 'reskilling initiatives'],
  },
  {
    id: 2,
    name: 'Coherence & Cohesion',
    code: 'CC',
    score: '7.0 / 9.0',
    band: 7.0,
    desc: 'Information is logically organized with clear progression and cohesive devices.',
    feedback: 'Paragraphs each hold a distinct focus; transitions flow smoothly with accurate linkers.',
    highlights: ['Consequently', 'In contrast', 'From an economic standpoint'],
  },
  {
    id: 3,
    name: 'Lexical Resource',
    code: 'LR',
    score: '8.0 / 9.0',
    band: 8.0,
    desc: 'Wide range of vocabulary with very natural, sophisticated collocations and precise usage.',
    feedback: "Excellent academic style: 'alleviate workforce displacement', 'technological singularity'.",
    highlights: ['workforce displacement', 'synergistic symbiosis', 'ubiquitous integration'],
  },
  {
    id: 4,
    name: 'Grammatical Range & Accuracy',
    code: 'GRA',
    score: '7.5 / 9.0',
    band: 7.5,
    desc: 'Wide range of complex structures used with good flexibility and rare minor errors.',
    feedback: 'Skillful conditional clauses, passive constructions, and varied sentence openings.',
    highlights: ['Were governments to intervene', 'not only mitigates but also enhances'],
  },
];

// CEFR Multi-level 4 Criteria
interface MultilevelCriterionData {
  id: number;
  name: string;
  code: string;
  score: string;
  max: number;
  percent: number;
  desc: string;
  feedback: string;
  highlights: string[];
}

const MULTILEVEL_4_CRITERIA: MultilevelCriterionData[] = [
  {
    id: 1,
    name: 'Content (Mavzu mazmuni)',
    code: 'CONTENT',
    score: '4.5 / 5.0',
    max: 5,
    percent: 90,
    desc: "Topshiriqdagi barcha bandlar to'liq, dalillar va mantiqiy asoslar bilan yoritilgan.",
    feedback: "Taklif etilgan velosiped ijarasi tizimi shahardagi tirbandlikni kamaytirish va ekologiyani yaxshilashga qaratilgan amaliy takliflar bilan to'liq ochib berilgan.",
    highlights: ['practical recommendations', 'urban transit', 'congestion relief'],
  },
  {
    id: 2,
    name: 'Communicative Achievement (Registr)',
    code: 'COMM',
    score: '4.0 / 5.0',
    max: 5,
    percent: 80,
    desc: "Rasmiy xat shakli, odob va munosib ishchan uslub (formal register) saqlangan.",
    feedback: "Shahar hokimiyatiga murojaat uchun mos muloyim va professional iboralar qo'llangan ('I would urge the council to consider...').",
    highlights: ['formal register', 'polite persuasion', 'appropriate tone'],
  },
  {
    id: 3,
    name: 'Organisation (Matn tuzilishi)',
    code: 'ORG',
    score: '4.5 / 5.0',
    max: 5,
    percent: 90,
    desc: "Paragraflar mantiqiy ketma-ketlikda tuzilgan va bog'lovchi vositalar bilan bog'langan.",
    feedback: "Kirish, asosiy takliflar va xulosa aniq ajratilgan. 'Furthermore', 'Consequently', 'To mitigate this challenge' kabi bog'lovchilar o'rinli ishlatilgan.",
    highlights: ['Furthermore', 'Consequently', 'To mitigate this challenge'],
  },
  {
    id: 4,
    name: 'Language (Leksika va grammatika)',
    code: 'LANG',
    score: '4.0 / 5.0',
    max: 5,
    percent: 80,
    desc: "CEFR C1 darajasiga mos boy so'z boyligi va murakkab sintaktik tuzilmalar.",
    feedback: "'sustainable transit infrastructure', 'alleviate commuter bottleneck', 'subsidize operational costs' kabi ilg'or leksika qo'llangan.",
    highlights: ['sustainable transit infrastructure', 'alleviate commuter bottleneck', 'subsidize'],
  },
];

// Attestation 2026 Categories & Diagnostics
interface AttestationCategory {
  id: number;
  name: string;
  total: number;
  correct: number;
  percent: number;
  desc: string;
}

const ATTESTATION_CATEGORIES: AttestationCategory[] = [
  {
    id: 1,
    name: 'Mutaxassislik fani (Ona tili va adabiyot)',
    total: 35,
    correct: 32,
    percent: 91.4,
    desc: "Grammatika, fonetika, leksikologiya va adabiyot tarixi bo'yicha chuqurlashtirilgan savollar.",
  },
  {
    id: 2,
    name: "Kasbiy standart va me'yoriy hujjatlar",
    total: 5,
    correct: 5,
    percent: 100,
    desc: "Xalq ta'limi tizimi qonunchiligi, o'qituvchi kasbiy standarti va etikasi.",
  },
  {
    id: 3,
    name: 'Pedagogik mahorat va baholash metodikasi',
    total: 10,
    correct: 9,
    percent: 90,
    desc: "Formativ baholash, inklyuziv ta'lim, darsni rejalashtirish va interaktiv metodlar.",
  },
];

interface MiniCbtQuestion {
  id: number;
  subject: string;
  badge: string;
  passage?: string;
  passageLabel?: string;
  question: string;
  options: { key: string; text: string; correct?: boolean }[];
  explanation: string;
}

const CBT_QUESTIONS_UZBEK: MiniCbtQuestion[] = [
  {
    id: 1,
    subject: 'Ona tili va adabiyot (Milliy Sertifikat)',
    badge: 'Rasmiy BMB 2026 • 1/3',
    passageLabel: 'Badiiy matn tahlili',
    passage: "Alisher Navoiy 'Hayrat ul-abror' dostonida insoniylik, odob va nutq madaniyatiga alohida fasllar bag'ishlaydi.",
    question: "Navoiyning 'Hayrat ul-abror' dostonida keltirilgan 'Sher va durroj' masalining asosiy g'oyaviy xulosasi nimadan iborat?",
    options: [
      { key: 'A', text: "Ilm olish va ustozga ehtirom ko'rsatish" },
      { key: 'B', text: "Tilga ehtiyot bo'lish, noo'rin so'zlash balosidan ogoh bo'lish", correct: true },
      { key: 'C', text: "Saxovat va saxiylik fazilatining ulug'ligi" },
      { key: 'D', text: "Davlatni boshqarish va podshohlar adolati" },
    ],
    explanation: "To'g'ri javob: B. Masalda durroj qushining noo'rin sayrashi uning ovchi tomonidan ushlanishiga sabab bo'lgani bayon qilinib, tilni tiyish o'rgatiladi.",
  },
  {
    id: 2,
    subject: 'Ona tili va adabiyot (Milliy Sertifikat)',
    badge: 'Rasmiy BMB 2026 • 2/3',
    passageLabel: 'Sintaksis & Tinish belgilari',
    passage: "Qo'shma gaplarda sodda gaplarning o'zaro mazmuniy bog'lanishi va tinish belgilari me'yorlariga qat'iy rioya etilishi talab qilinadi.",
    question: "Qaysi gapda tinish belgisi qo'llanishi bilan bog'liq xatolikka yo'l qo'yilgan?",
    options: [
      { key: 'A', text: "Daraxtlar shoxlari qordan egildi, havo esa borgan sari iliy boshladi." },
      { key: 'B', text: "U na kitob o'qidi, na darslarini tayyorladi va imtihondan past ball oldi." },
      { key: 'C', text: "Quyosh ufqqa bosh qo'ydi: qorong'ilik butun vodiyni o'z domiga tortdi." },
      { key: 'D', text: "Yurtini sevgan inson — har qanday qiyinchilikka chidaydi, chunki unda yuksak mas'uliyat bor.", correct: true },
    ],
    explanation: "To'g'ri javob: D. Bu o'rinda ega va kesim orasida chiziqcha qo'yilishi xato, chunki kesim oldida ergashgan sabab ergash gap mavjud emas, bog'lovchi yordamida ajratilgan.",
  },
  {
    id: 3,
    subject: 'Ona tili va adabiyot (Milliy Sertifikat)',
    badge: 'Rasmiy BMB 2026 • 3/3',
    passageLabel: 'Leksikologiya & Uslubiyat',
    passage: "So'zlarning ma'no nozikliklarini his qilmaslik va kalka birikmalarni qo'llash nutqning ta'sirchanligini pasaytiradi.",
    question: "Qaysi javobda nutqiy g'alizlik (uslubiy xatolik) kuzatiladi?",
    options: [
      { key: 'A', text: "Ushbu muammo bo'yicha yig'ilishda qizg'in bahs-munozara bo'lib o'tdi." },
      { key: 'B', text: "Yoshlarning ma'naviy dunyoqarashini boyitish — dolzarb vazifa." },
      { key: 'C', text: "Ushbu qaror viloyat miqyosida o'z aksini topdi va ijroga yo'naltirildi.", correct: true },
      { key: 'D', text: "Konferensiya qatnashchilari o'z ma'ruzalari bilan faol ishtirok etdilar." },
    ],
    explanation: "To'g'ri javob: C. 'O'z aksini topdi' birikmasi ruschadagi 'нашло своё отражение' iborasining kalkasi bo'lib, o'zbek adabiy tilida 'o'z aksini ko'rsatdi' yoki 'aks etdi' deyilishi to'g'riroq.",
  },
];

const CBT_QUESTIONS_ATTESTATION: MiniCbtQuestion[] = [
  {
    id: 1,
    subject: 'Pedagogik mahorat & Metodika (Savol #38)',
    badge: 'Attestatsiya 2026 • 1/3',
    passageLabel: 'Metodik keys tahlili',
    passage: "O'quvchilarning mustaqil fikrlashi va mas'uliyatini oshirish uchun zamonaviy formativ baholash vositalari qo'llaniladi.",
    question: "Dars jarayonida formativ baholash (assessment for learning) vositalaridan foydalanishda o'quvchining o'z-o'zini baholash (self-assessment) qobiliyatini rivojlantirish uchun eng samarali usul qaysi?",
    options: [
      { key: 'A', text: "Faqat chorak oxirida yakuniy test natijalariga qarab reyting e'lon qilish" },
      { key: 'B', text: "O'quvchilarga aniq deskriptorli rubrika berib, o'z ishini tekshirish va xatolar ustida refleksiya qilishga undash", correct: true },
      { key: 'C', text: "O'quvchilar javoblarini faqat o'zaro solishtirib differensial ball qo'yish" },
      { key: 'D', text: "Barcha mustaqil topshiriqlarni faqat o'qituvchi tomonidan baholab berish" },
    ],
    explanation: "To'g'ri javob: B. O'z-o'zini baholash (self-assessment) samarali bo'lishi uchun o'quvchi aniq mezonlar (rubrics) asosida o'z natijasini baholashi va xatolarini mustaqil tahlil qilishi lozim.",
  },
  {
    id: 2,
    subject: 'Pedagogik mahorat & Metodika (Savol #42)',
    badge: 'Attestatsiya 2026 • 2/3',
    passageLabel: 'Blum taksonomiyasi',
    passage: "Bilish, tushunish, qo'llash, tahlil, sintez va baholash bosqichlari o'quvchining kognitiv faoliyatini tizimlashtiradi.",
    question: "Blum taksonomiyasining 'Tahlil' (Analysis) darajasiga mos keluvchi topshiriq turini aniqlang:",
    options: [
      { key: 'A', text: "Mavzuga oid asosiy qoidalar va formulalarni yoddan aytib berish" },
      { key: 'B', text: "O'rganilgan formuladan foydalanib standart matematik masalani yechish" },
      { key: 'C', text: "Berilgan ikki badiiy asar qahramonlarining xatti-harakatlarini qiyoslab, sabab-oqibat zanjirini tuzish", correct: true },
      { key: 'D', text: "Muammo yuzasidan yangi muqobil ilmiy loyiha konsepsiyasini ishlab chiqish" },
    ],
    explanation: "To'g'ri javob: C. Sabab-oqibatni aniqlash va qiyosiy tahlil qilish 'Tahlil' bosqichiga taalluqli; yangi loyiha yaratish esa 'Sintez/Yaratish' darajasidir.",
  },
  {
    id: 3,
    subject: 'Pedagogik mahorat & Metodika (Savol #47)',
    badge: 'Attestatsiya 2026 • 3/3',
    passageLabel: "Diferensial ta'lim",
    passage: "Sinfdagi o'quvchilarning o'zlashtirish tezligi va qobiliyatlari turlicha bo'lgan sharoitda yakka tartibdagi yondashuv talab etiladi.",
    question: "Turli darajadagi o'quvchilar bilan ishlashda eng samarali pedagogik strategiya qaysi?",
    options: [
      { key: 'A', text: "Tabaqalashtirilgan topshiriqlar (Tiered assignments) va moslashtirilgan ko'rsatmalar taqdim etish", correct: true },
      { key: 'B', text: "Faqat a'lochi o'quvchilar sur'atiga moslashgan umumiy dars rejasini olib borish" },
      { key: 'C', text: "Past o'zlashtiruvchi o'quvchilarga umuman mustaqil vazifa bermaslik" },
      { key: 'D', text: "Dars davomida faqat eng oson darajadagi savollardan foydalanish" },
    ],
    explanation: "To'g'ri javob: A. Tabaqalashtirilgan topshiriqlar har bir o'quvchining o'z zonasida rivojlanishiga (Vigotskiy yaqin rivojlanish zonasi) imkoniyat yaratadi.",
  },
];

const CBT_QUESTIONS_IELTS: MiniCbtQuestion[] = [
  {
    id: 1,
    subject: 'Cambridge IELTS (Academic Reading)',
    badge: 'Cambridge Model • 1/3',
    passageLabel: 'Cognitive Science Passage',
    passage: "Spaced retrieval practice optimizes synaptic consolidation by interrupting memory decay curves at precise neurocognitive intervals.",
    question: "Why does spaced repetition outperform massed cramming in long-term memory retention?",
    options: [
      { key: 'A', text: 'It completely eliminates the necessity for active retrieval cues' },
      { key: 'B', text: 'It forces neural pathways to reconsolidate memory traces at optimal decay intervals', correct: true },
      { key: 'C', text: 'It bypasses the prefrontal cortex directly into procedural memory' },
      { key: 'D', text: 'It reduces neurotransmitter depletion during single 20-minute sessions' },
    ],
    explanation: "Correct answer: B. Cognitive retrieval research demonstrates that testing memory at expanding intervals forces synaptic re-encoding.",
  },
  {
    id: 2,
    subject: 'Cambridge IELTS (Academic Reading)',
    badge: 'Cambridge Model • 2/3',
    passageLabel: 'Linguistic Analysis',
    passage: "Academic discourse strictly requires stylistic objectivity, avoiding emotive language in empirical reporting.",
    question: "Which of the following sentences exhibits appropriate academic register and precision?",
    options: [
      { key: 'A', text: 'The results were totally crazy and shocked everyone in the lab.' },
      { key: 'B', text: 'Researchers got pretty lucky when the reaction miraculously succeeded.' },
      { key: 'C', text: 'The empirical data substantiates the hypothesis that urban density correlates with transit efficiency.', correct: true },
      { key: 'D', text: 'It is super obvious that traffic jams cause big problems for city folks.' },
    ],
    explanation: "Correct answer: C. 'Substantiates the hypothesis', 'correlates with', and 'transit efficiency' reflect authentic C1/Band 8.0 academic collocations.",
  },
  {
    id: 3,
    subject: 'Cambridge IELTS (Academic Reading)',
    badge: 'Cambridge Model • 3/3',
    passageLabel: 'Inference & Context',
    passage: "While decentralized microgrids exhibit higher upfront installation expenses, their lifecycle resilience during grid-wide blackouts yields net positive socioeconomic dividends.",
    question: "What underlying assumption does the author make concerning decentralized energy grids?",
    options: [
      { key: 'A', text: 'Their enduring operational resilience outweighs initial capital expenditure over time', correct: true },
      { key: 'B', text: 'They will render traditional power plants completely obsolete within three years' },
      { key: 'C', text: 'They require zero maintenance once connected to municipal substations' },
      { key: 'D', text: 'They are economically viable only in desert and coastal microclimates' },
    ],
    explanation: "Correct answer: A. 'Yields net positive socioeconomic dividends' directly supports the long-term cost-benefit superiority of resilient microgrids.",
  },
];

const CBT_QUESTIONS_MULTILEVEL: MiniCbtQuestion[] = [
  {
    id: 1,
    subject: 'CEFR Multi-level (Reading Part 3)',
    badge: 'CEFR C1 • 1/3',
    passageLabel: 'Applied Technology Text',
    passage: "Decentralized renewable microgrids allow localized power distribution without sole reliance on the traditional central power grid during peak surge hours.",
    question: "What is identified as the primary operational advantage of decentralized microgrids during peak demand?",
    options: [
      { key: 'A', text: 'They eliminate the necessity of electrical substations entirely' },
      { key: 'B', text: 'They distribute battery storage dynamically, preventing central grid overloads', correct: true },
      { key: 'C', text: 'They reduce initial capital expenditures by over eighty percent' },
      { key: 'D', text: 'They depend exclusively on wind generation without battery storage' },
    ],
    explanation: "Correct answer: B. The passage emphasizes that localized distribution with dynamic battery storage buffers peak demand, avoiding grid-wide failure.",
  },
  {
    id: 2,
    subject: 'CEFR Multi-level (Grammar & Cohesion)',
    badge: 'CEFR C1 • 2/3',
    passageLabel: 'Advanced Syntax Test',
    passage: "Inversion is utilized in formal and academic English to emphasize conditional or restrictive adverbial clauses.",
    question: "Which sentence accurately utilizes negative inversion for formal emphasis?",
    options: [
      { key: 'A', text: 'Seldom students have exhibited such dedication to autonomous linguistic mastery.' },
      { key: 'B', text: 'Never he had seen such remarkable advances in computational linguistics.' },
      { key: 'C', text: 'Scarcely had the regulatory framework been ratified when market demand surged exponentially.', correct: true },
      { key: 'D', text: 'Rarely we encounter such pristine archaeological artifacts in this stratum.' },
    ],
    explanation: "Correct answer: C. 'Scarcely had + subject + past participle ... when ...' is the grammatically precise C1 inversion construction.",
  },
  {
    id: 3,
    subject: 'CEFR Multi-level (Lexical Precision)',
    badge: 'CEFR C1 • 3/3',
    passageLabel: 'Idiomatic Register',
    passage: "Contextual nuance distinguishes proficient communicators from intermediate learners in executive correspondence.",
    question: "Choose the most appropriate collocation to complete: 'The municipal committee decided to ________ the bureaucratic procedure.'",
    options: [
      { key: 'A', text: 'quicken down' },
      { key: 'B', text: 'smooth run' },
      { key: 'C', text: 'fast forwardly enact' },
      { key: 'D', text: 'streamline', correct: true },
    ],
    explanation: "Correct answer: D. 'Streamline the procedure/process' is the standard C1 idiomatic collocation for making an organization or process more efficient.",
  },
];

const SPEAKING_DEMO = {
  part: 'IELTS Speaking Part 2 (Cue Card)',
  topic: 'Describe an artificial intelligence tool you recently used that boosted your productivity.',
  targetScore: 'Band 7.5',
  scores: {
    fluency: 7.5,
    pronunciation: 8.0,
    lexical: 8.0,
    grammar: 7.5,
  },
  transcript:
    "'Over the past six months, I have extensively utilized an AI-driven learning platform that generates tailored spaced repetition quizzes. What struck me most was its ability to instantly synthesize complex academic passages into bite-sized retrieval questions, which markedly optimized my preparation schedule.'",
  feedback:
    "Natural discourse markers, minimal hesitation, consistent intonation rhythm, and precise academic collocations ('synthesize', 'retrieval', 'markedly').",
};

// Top navigation anchor links
const sectionNav: [string, string][] = [
  ['nav_features', '#features'],
  ['nav_how', '#how-it-works'],
  ['nav_comparison', '#comparison'],
  ['nav_pricing', '#pricing'],
  ['nav_faq', '#faq'],
];

export default function Landing() {
  const { t } = useLang();
  const { user, openAuthModal } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  // -------------------------------------------------------------------------
  // HIERARCHICAL 2-LEVEL SUBJECT & EXAM SELECTOR STATE
  // -------------------------------------------------------------------------
  const [landingSubject, setLandingSubject] = useState<MainSubject>(() => {
    const track = localStorage.getItem('grandec_selected_track');
    if (track === 'ielts' || track === 'multilevel') return 'english';
    if (track === 'national_certificate' || track === 'attestation') return 'uzbek';
    const saved = localStorage.getItem('landing_subject') || localStorage.getItem('lms_subject');
    return saved === 'english' ? 'english' : 'uzbek';
  });

  const [selectedTrack, setSelectedTrack] = useState<ExamTrack>(() => {
    const track = localStorage.getItem('grandec_selected_track') as ExamTrack | null;
    if (track && ['ielts', 'multilevel', 'national_certificate', 'attestation'].includes(track)) {
      return track;
    }
    const savedSub = localStorage.getItem('landing_subject') || localStorage.getItem('lms_subject');
    return savedSub === 'english' ? 'ielts' : 'national_certificate';
  });

  const handleSubjectSwitch = (sub: MainSubject) => {
    if (sub === landingSubject) return;
    setLandingSubject(sub);
    let newTrack: ExamTrack = sub === 'english' ? 'ielts' : 'national_certificate';
    if (sub === 'english' && (selectedTrack === 'ielts' || selectedTrack === 'multilevel')) {
      newTrack = selectedTrack;
    } else if (sub === 'uzbek' && (selectedTrack === 'national_certificate' || selectedTrack === 'attestation')) {
      newTrack = selectedTrack;
    }
    setSelectedTrack(newTrack);
    localStorage.setItem('landing_subject', sub);
    localStorage.setItem('lms_subject', sub);
    localStorage.setItem('grandec_selected_track', newTrack);
    window.dispatchEvent(new CustomEvent('subject-changed', { detail: sub }));
  };

  const handleTrackSwitch = (track: ExamTrack) => {
    setSelectedTrack(track);
    const sub: MainSubject = track === 'ielts' || track === 'multilevel' ? 'english' : 'uzbek';
    setLandingSubject(sub);
    localStorage.setItem('landing_subject', sub);
    localStorage.setItem('lms_subject', sub);
    localStorage.setItem('grandec_selected_track', track);
    window.dispatchEvent(new CustomEvent('subject-changed', { detail: sub }));
  };

  // Demo tabs per track
  const [demoTabIelts, setDemoTabIelts] = useState<'writing' | 'speaking' | 'cbt'>('writing');
  const [demoTabMultilevel, setDemoTabMultilevel] = useState<'writing' | 'cbt'>('writing');
  const [demoTabNatCert, setDemoTabNatCert] = useState<'essay' | 'test'>('essay');
  const [demoTabAttestation, setDemoTabAttestation] = useState<'test' | 'diagnostic'>('test');

  // Selected criterion details
  const [selectedCritNatCert, setSelectedCritNatCert] = useState<CriterionData>(ESSAY_12_CRITERIA[0]);
  const [selectedCritIelts, setSelectedCritIelts] = useState<IeltsCriterionData>(IELTS_4_CRITERIA[0]);
  const [selectedCritMultilevel, setSelectedCritMultilevel] = useState<MultilevelCriterionData>(MULTILEVEL_4_CRITERIA[0]);

  // Mini CBT 3-question interactive simulators
  const [cbtIndexNatCert, setCbtIndexNatCert] = useState(0);
  const [cbtAnswersNatCert, setCbtAnswersNatCert] = useState<Record<number, string>>({});
  const [cbtFinishedNatCert, setCbtFinishedNatCert] = useState(false);

  const [cbtIndexAttestation, setCbtIndexAttestation] = useState(0);
  const [cbtAnswersAttestation, setCbtAnswersAttestation] = useState<Record<number, string>>({});
  const [cbtFinishedAttestation, setCbtFinishedAttestation] = useState(false);

  const [cbtIndexIelts, setCbtIndexIelts] = useState(0);
  const [cbtAnswersIelts, setCbtAnswersIelts] = useState<Record<number, string>>({});
  const [cbtFinishedIelts, setCbtFinishedIelts] = useState(false);

  const [cbtIndexMultilevel, setCbtIndexMultilevel] = useState(0);
  const [cbtAnswersMultilevel, setCbtAnswersMultilevel] = useState<Record<number, string>>({});
  const [cbtFinishedMultilevel, setCbtFinishedMultilevel] = useState(false);

  const handleAnswerQuestion = (
    track: 'nat' | 'attest' | 'ielts' | 'multi',
    qIndex: number,
    optKey: string,
    isCorrect: boolean,
  ) => {
    if (track === 'nat') {
      setCbtAnswersNatCert((prev) => ({ ...prev, [qIndex]: optKey }));
    } else if (track === 'attest') {
      setCbtAnswersAttestation((prev) => ({ ...prev, [qIndex]: optKey }));
    } else if (track === 'ielts') {
      setCbtAnswersIelts((prev) => ({ ...prev, [qIndex]: optKey }));
    } else if (track === 'multi') {
      setCbtAnswersMultilevel((prev) => ({ ...prev, [qIndex]: optKey }));
    }
    if (isCorrect) {
      try {
        confetti({
          particleCount: 35,
          spread: 60,
          origin: { y: 0.65 },
          colors: ['#10B981', '#34D399', '#6EE7B7'],
        });
      } catch {
        /* ignore */
      }
    }
  };

  // Speaking playback state
  const [isSpeakingPlaying, setIsSpeakingPlaying] = useState<boolean>(false);

  // Live platform stats
  const [stats, setStats] = useState<{
    totals: { tests: number; students: number; essays_graded: number };
    daily?: { labels: string[]; attempts: number[]; avg: number[] };
  } | null>(null);

  const trendData = useMemo<TrendPoint[]>(() => {
    if (!stats?.daily?.labels) return [];
    const { labels, attempts, avg } = stats.daily;
    return labels.map((l, i) => ({
      date: l,
      attempts: attempts[i] ?? 0,
      avg: avg[i] ?? 0,
      certs: 0,
      students: 0,
      essays: 0,
    }));
  }, [stats]);

  const startTo = user ? landingFor(user) : '/register';

  useEffect(() => {
    let live = true;
    School.publicStats()
      .then((s) => {
        if (live) setStats(s);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  // Lock scroll on mobile drawer
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  // Option click handlers with celebratory confetti






  const handleAction = (destination: string) => {
    localStorage.setItem('grandec_selected_track', selectedTrack);
    localStorage.setItem('landing_subject', landingSubject);
    localStorage.setItem('lms_subject', landingSubject);
    if (user) {
      navigate(destination);
    } else {
      openAuthModal('register');
    }
  };

  // SEO schema
  const jsonLdData = useMemo(
    () => [
      {
        '@context': 'https://schema.org',
        '@type': 'EducationalOrganization',
        name: 'GRAND EDUCATION LMS',
        url: 'https://grandec.uz',
        logo: 'https://grandec.uz/grandec.png',
        description:
          "Milliy sertifikat (Ona tili) va IELTS & Multi-level (Ingliz tili) bo'yicha AI Esse, AI Speaking va CBT test platformasi.",
        sameAs: ['https://t.me/uz_essaygrader_bot'],
      },
    ],
    [],
  );

  return (
    <div
      className="landing"
      style={{
        background: 'var(--bg)',
        color: 'var(--ink)',
        minHeight: '100svh',
        position: 'relative',
        overflowX: 'clip',
      }}
    >
      <SEO
        title={
          selectedTrack === 'ielts'
            ? 'IELTS Academic & General LMS | AI Writing & Speaking Simulator'
            : selectedTrack === 'multilevel'
            ? 'CEFR Multi-level LMS | Davlat BMB Imtihoni & AI Insho'
            : selectedTrack === 'attestation'
            ? 'Pedagoglar Attestatsiyasi 2026 | 70% Ustama & Toifa Testlari'
            : 'Ona tili va adabiyot LMS | Milliy sertifikat & AI Esse'
        }
        description={
          selectedTrack === 'ielts'
            ? "IELTS Band 1.0–9.0 bo'yicha Writing Task 1 & 2 AI baholash, interaktiv Speaking trenajyori va Cambridge CBT Listening/Reading — GRAND EDUCATION."
            : selectedTrack === 'multilevel'
            ? "Davlat CEFR Multi-level (B2/C1) imtihoniga tayyorlovchi rasmiy CBT testlar va AI Writing insho tahlili."
            : selectedTrack === 'attestation'
            ? "O'qituvchilar attestatsiyasi 2026: 50 talik rasmiy sinov (mutaxassislik, kasbiy standart, pedagogik mahorat) va toifa diagnostikasi."
            : "BMB Davlat standarti bo'yicha 12 ta mezonli AI Esse tahlili, 45 talik testlar va 1v1 intellektual Arena."
        }
        jsonLd={jsonLdData}
      />

      {/* Global Background Glow */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 'min(1200px, 100vw)',
          height: 600,
          background:
            landingSubject === 'english'
              ? 'radial-gradient(circle at 50% 20%, rgba(56, 189, 248, 0.15), rgba(99, 102, 241, 0.08) 40%, transparent 70%)'
              : 'radial-gradient(circle at 50% 20%, rgba(245, 158, 11, 0.15), rgba(139, 92, 246, 0.08) 40%, transparent 70%)',
          pointerEvents: 'none',
          zIndex: 0,
          transition: 'background 0.4s ease',
        }}
      />

      {/* NAVBAR */}
      <header
        className="landing-header"
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          background: 'var(--header-bg)',
          borderBottom: '1px solid var(--border)',
          transition: 'background 0.3s ease, border-color 0.3s ease',
        }}
      >
        <div
          style={{
            margin: '0 auto',
            maxWidth: 1200,
            padding: '12px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          {/* Brand Logo */}
          <Link
            to="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            <img
              src="/grandec.png"
              alt="GRAND EDUCATION"
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                objectFit: 'cover',
                boxShadow:
                  landingSubject === 'english'
                    ? '0 0 16px rgba(56, 189, 248, 0.35)'
                    : '0 0 16px rgba(245, 158, 11, 0.35)',
              }}
            />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 900,
                  letterSpacing: '-0.02em',
                  color: 'var(--ink)',
                  lineHeight: 1.1,
                }}
              >
                GRAND EDUCATION
              </span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: '0.12em',
                  color: landingSubject === 'english' ? '#38BDF8' : '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {selectedTrack === 'ielts'
                  ? 'IELTS Band 7.5+ AI'
                  : selectedTrack === 'multilevel'
                  ? 'CEFR Multi-level (B2/C1)'
                  : selectedTrack === 'attestation'
                  ? 'Attestatsiya 2026'
                  : 'Milliy Sertifikat'}
              </span>
            </div>
          </Link>

          {/* Desktop Nav Anchors */}
          <div
            className="landing-desktop-nav"
            style={{
              display: 'none',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {sectionNav.map(([k, href]) => (
              <a
                key={k}
                href={href}
                style={{
                  padding: '8px 14px',
                  borderRadius: 10,
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--muted)',
                  textDecoration: 'none',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--ink)';
                  e.currentTarget.style.background = 'var(--dropdown-hover)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--muted)';
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                {t(k)}
              </a>
            ))}
          </div>

          {/* Right Area: Language Switcher, Theme Switcher & Auth / User Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {user ? (
              <UserNavDropdown />
            ) : (
              <>
                <LanguageSwitcher />
                <button
                  type="button"
                  onClick={() => setTheme(resolvedTheme === 'light' ? 'dark' : 'light')}
                  title={resolvedTheme === 'light' ? "Qorong'i rejimga o'tish" : "Yorug' rejimga o'tish"}
                  aria-label={resolvedTheme === 'light' ? "Qorong'i rejim" : "Yorug' rejim"}
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                    color: 'var(--ink)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {resolvedTheme === 'light' ? <MoonIcon size={16} /> : <SunIcon size={16} />}
                </button>
                <button
                  type="button"
                  onClick={() => openAuthModal('login')}
                  className="btn-glow"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '9px 20px',
                    borderRadius: 12,
                    fontSize: 14,
                    fontWeight: 800,
                    color: '#090d16',
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    border: 'none',
                    cursor: 'pointer',
                    boxShadow: '0 4px 16px rgba(245, 158, 11, 0.35)',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <span>{t('login')}</span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 800,
                      padding: '2px 6px',
                      borderRadius: 6,
                      background: 'rgba(9, 13, 22, 0.2)',
                    }}
                  >
                    1-klik
                  </span>
                </button>
              </>
            )}

            {/* Mobile Hamburger */}
            <button
              type="button"
              className="landing-burger-btn"
              onClick={() => setMobileOpen(true)}
              aria-label="Menyu ochish"
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                background: 'var(--card-2)',
                border: '1px solid var(--border)',
                color: 'var(--ink)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <MenuIcon size={20} />
            </button>
          </div>
        </div>
      </header>

      {/* MOBILE DRAWER */}
      {mobileOpen && (
        <div style={{ position: 'relative', zIndex: 100 }}>
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(4, 7, 13, 0.75)',
              backdropFilter: 'blur(10px)',
              WebkitBackdropFilter: 'blur(10px)',
            }}
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: '85%',
              maxWidth: 340,
              zIndex: 100,
              background: 'var(--card)',
              borderLeft: '1px solid var(--border)',
              padding: '24px 20px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '-12px 0 40px rgba(0, 0, 0, 0.5)',
            }}
            role="dialog"
            aria-modal="true"
            aria-label="Mobil navigatsiya"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <img src="/grandec.png" alt="GRANDEC" style={{ width: 30, height: 30 }} />
                <span style={{ fontWeight: 900, fontSize: 16, color: 'var(--ink)' }}>GRAND EDUCATION</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--muted)',
                  cursor: 'pointer',
                }}
              >
                <XIcon size={20} />
              </button>
            </div>

            <nav style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
              {sectionNav.map(([k, href]) => (
                <a
                  key={k}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 12,
                    fontSize: 15,
                    fontWeight: 600,
                    color: 'var(--muted)',
                    textDecoration: 'none',
                  }}
                >
                  {t(k)}
                </a>
              ))}
            </nav>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 20 }}>
              {user ? (
                <Link
                  to={startTo}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    color: '#090d16',
                    fontWeight: 800,
                    fontSize: 14,
                    textDecoration: 'none',
                  }}
                >
                  {formatDisplayName(user.full_name, user.email)} →
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setMobileOpen(false);
                    openAuthModal('login');
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    color: '#090d16',
                    fontWeight: 800,
                    fontSize: 14,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {t('login')} (1-klik)
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MAIN CONTENT WRAPPER */}
      <main id="main-content">
        {/* HERO SECTION */}
        <section id="hero" style={{ padding: '36px 20px 60px' }}>
          <div
            style={{
              margin: '0 auto',
              maxWidth: 1200,
            }}
          >
            {/* 2-LEVEL HIERARCHICAL SELECTOR (Subject & Exam Selector) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28 }}>
              {/* Level 1: Main Subject Switcher */}
              <div
                role="group"
                aria-label="Asosiy fanni tanlang"
                className="hero-subject-switcher"
              >
                {/* 🇺🇿 Ona tili */}
                <button
                  type="button"
                  onClick={() => handleSubjectSwitch('uzbek')}
                  className={`hero-switcher-btn ${landingSubject === 'uzbek' ? 'active' : ''}`}
                  aria-pressed={landingSubject === 'uzbek'}
                >
                  <span style={{ fontSize: 18 }}>🇺🇿</span>
                  <span>{t('hero_sub_uzbek_title')}</span>
                  <span className="switcher-subtag">{t('hero_sub_uzbek_tag')}</span>
                </button>

                {/* 🇬🇧 English */}
                <button
                  type="button"
                  onClick={() => handleSubjectSwitch('english')}
                  className={`hero-switcher-btn ${landingSubject === 'english' ? 'active' : ''}`}
                  aria-pressed={landingSubject === 'english'}
                >
                  <span style={{ fontSize: 18 }}>🇬🇧</span>
                  <span>{t('hero_sub_english_title')}</span>
                  <span className="switcher-subtag">{t('hero_sub_english_tag')}</span>
                </button>
              </div>

              {/* Level 2: Exam Direction Switcher */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={landingSubject}
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.18 }}
                  className="hero-exam-switcher"
                  role="group"
                  aria-label={t('hero_exam_select_aria')}
                >
                  {landingSubject === 'english' ? (
                    <>
                      <button
                        type="button"
                        onClick={() => handleTrackSwitch('ielts')}
                        className={`hero-exam-btn ${selectedTrack === 'ielts' ? 'active active-eng' : ''}`}
                        aria-pressed={selectedTrack === 'ielts'}
                      >
                        <span style={{ fontSize: 16 }}>🎓</span>
                        <span>{t('hero_track_ielts_title')}</span>
                        <span className="exam-btn-badge">{t('hero_track_ielts_badge')}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleTrackSwitch('multilevel')}
                        className={`hero-exam-btn ${selectedTrack === 'multilevel' ? 'active active-eng' : ''}`}
                        aria-pressed={selectedTrack === 'multilevel'}
                      >
                        <span style={{ fontSize: 16 }}>🎯</span>
                        <span>{t('hero_track_multilevel_title')}</span>
                        <span className="exam-btn-badge">{t('hero_track_multilevel_badge')}</span>
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => handleTrackSwitch('national_certificate')}
                        className={`hero-exam-btn ${selectedTrack === 'national_certificate' ? 'active active-uz' : ''}`}
                        aria-pressed={selectedTrack === 'national_certificate'}
                      >
                        <span style={{ fontSize: 16 }}>🎓</span>
                        <span>{t('hero_track_national_title')}</span>
                        <span className="exam-btn-badge">{t('hero_track_national_badge')}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleTrackSwitch('attestation')}
                        className={`hero-exam-btn ${selectedTrack === 'attestation' ? 'active active-uz' : ''}`}
                        aria-pressed={selectedTrack === 'attestation'}
                      >
                        <span style={{ fontSize: 16 }}>👨‍🏫</span>
                        <span>{t('hero_track_attestation_title')}</span>
                        <span className="exam-btn-badge">{t('hero_track_attestation_badge')}</span>
                      </button>
                    </>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>

            {/* HERO GRID */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr',
                gap: 44,
                alignItems: 'center',
              }}
              className="hero-grid"
            >
              {/* Left Column: Dynamic Headlines & 1-Click CTAs */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={selectedTrack}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.22, ease: 'easeOut' }}
                >
                  {/* Dynamic Badge */}
                  <div style={{ marginBottom: 20 }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '6px 16px',
                        borderRadius: 999,
                        fontSize: 12,
                        fontWeight: 700,
                        background:
                          landingSubject === 'english'
                            ? 'rgba(56, 189, 248, 0.12)'
                            : 'rgba(245, 158, 11, 0.1)',
                        color: landingSubject === 'english' ? '#38BDF8' : '#F59E0B',
                        border:
                          landingSubject === 'english'
                            ? '1px solid rgba(56, 189, 248, 0.3)'
                            : '1px solid rgba(245, 158, 11, 0.25)',
                        boxShadow:
                          landingSubject === 'english'
                            ? '0 0 20px rgba(56, 189, 248, 0.15)'
                            : '0 0 20px rgba(245, 158, 11, 0.1)',
                      }}
                    >
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: 999,
                          background: landingSubject === 'english' ? '#38BDF8' : '#10B981',
                          boxShadow: `0 0 10px ${landingSubject === 'english' ? '#38BDF8' : '#10B981'}`,
                        }}
                      />
                      {selectedTrack === 'ielts'
                        ? t('hero_pill_ielts')
                        : selectedTrack === 'multilevel'
                        ? t('hero_pill_multilevel')
                        : selectedTrack === 'attestation'
                        ? t('hero_pill_attestation')
                        : t('hero_pill_national')}
                    </span>
                  </div>

                  {/* Main Headline */}
                  <h1
                    style={{
                      fontSize: 'clamp(2.3rem, 4.8vw, 3.8rem)',
                      lineHeight: 1.12,
                      fontWeight: 900,
                      letterSpacing: '-0.03em',
                      color: 'var(--ink)',
                      margin: '0 0 20px',
                    }}
                  >
                    {selectedTrack === 'ielts' ? (
                      <>
                        {t('hero_h1_ielts_pre')}{' '}
                        <span className="hero-title-gradient">{t('hero_h1_ielts_grad')}</span>
                      </>
                    ) : selectedTrack === 'multilevel' ? (
                      <>
                        {t('hero_h1_multi_pre')}{' '}
                        <span className="hero-title-gradient">{t('hero_h1_multi_grad')}</span>
                      </>
                    ) : selectedTrack === 'attestation' ? (
                      <>
                        {t('hero_h1_attest_pre')}{' '}
                        <span className="hero-title-gradient">{t('hero_h1_attest_grad')}</span>
                      </>
                    ) : (
                      <>
                        {t('hero_h1_nat_pre')}{' '}
                        <span className="hero-title-gradient">{t('hero_h1_nat_grad')}</span>
                      </>
                    )}
                  </h1>

                  {/* Subhead */}
                  <p
                    style={{
                      fontSize: 'clamp(1.05rem, 1.8vw, 1.18rem)',
                      lineHeight: 1.7,
                      color: 'var(--muted)',
                      maxWidth: 540,
                      margin: '0 0 32px',
                    }}
                  >
                    {selectedTrack === 'ielts'
                      ? t('hero_sub_ielts')
                      : selectedTrack === 'multilevel'
                      ? t('hero_sub_multi')
                      : selectedTrack === 'attestation'
                      ? t('hero_sub_attest')
                      : t('hero_sub_nat')}
                  </p>

                  {/* 1-Click Action Buttons */}
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 14,
                      alignItems: 'center',
                      marginBottom: 28,
                    }}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        handleAction(
                          selectedTrack === 'ielts'
                            ? '/speaking'
                            : selectedTrack === 'multilevel'
                            ? '/tests'
                            : selectedTrack === 'attestation'
                            ? '/tests'
                            : '/essays',
                        )
                      }
                      className="btn-glow"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '14px 28px',
                        borderRadius: 14,
                        fontSize: 15,
                        fontWeight: 800,
                        color: '#090d16',
                        background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                        border: 'none',
                        cursor: 'pointer',
                        boxShadow: '0 4px 20px rgba(245, 158, 11, 0.4)',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <span>
                        {selectedTrack === 'ielts'
                          ? t('hero_cta_ielts_btn')
                          : selectedTrack === 'multilevel'
                          ? t('hero_cta_multi_btn')
                          : selectedTrack === 'attestation'
                          ? t('hero_cta_attest_btn')
                          : t('hero_cta_nat_btn')}
                      </span>
                      <span style={{ fontSize: 16 }}>→</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => (user ? navigate(startTo) : openAuthModal('login'))}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '13px 22px',
                        borderRadius: 14,
                        fontSize: 14,
                        fontWeight: 700,
                        color: 'var(--ink)',
                        background: 'var(--card-2)',
                        border: '1px solid var(--border)',
                        cursor: 'pointer',
                        backdropFilter: 'blur(12px)',
                        transition: 'all 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = 'var(--accent)';
                        e.currentTarget.style.background = 'var(--dropdown-hover)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'var(--border)';
                        e.currentTarget.style.background = 'var(--card-2)';
                      }}
                    >
                      <span>{t('hero_cta_login_1click')}</span>
                    </button>
                  </div>

                  {/* Trust Indicators */}
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '10px 24px',
                      fontSize: 13,
                      fontWeight: 600,
                      color: '#94a3b8',
                    }}
                  >
                    {selectedTrack === 'ielts' ? (
                      <>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          {t('hero_trust_ielts_1')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          {t('hero_trust_ielts_2')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          {t('hero_trust_ielts_3')}
                        </span>
                      </>
                    ) : selectedTrack === 'multilevel' ? (
                      <>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          {t('hero_trust_multi_1')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          {t('hero_trust_multi_2')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#6366F1' }} />
                          {t('hero_trust_multi_3')}
                        </span>
                      </>
                    ) : selectedTrack === 'attestation' ? (
                      <>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          {t('hero_trust_attest_1')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          {t('hero_trust_attest_2')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#3B82F6' }} />
                          {t('hero_trust_attest_3')}
                        </span>
                      </>
                    ) : (
                      <>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} className="text-emerald" style={{ color: '#10B981' }} />
                          {t('hero_trust_nat_1')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} className="text-amber" style={{ color: '#F59E0B' }} />
                          {t('hero_trust_nat_2')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} className="text-purple" style={{ color: '#8B5CF6' }} />
                          {t('hero_trust_nat_3')}
                        </span>
                      </>
                    )}
                  </div>
                </motion.div>
              </AnimatePresence>

              {/* Right Column: High-End Interactive Demo Widget */}
              <div>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={selectedTrack}
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.22, ease: 'easeOut' }}
                    className="glass-card lcard-hover demo-card"
                    style={{
                      borderRadius: 24,
                      padding: '24px 24px 28px',
                      backdropFilter: 'blur(16px)',
                      minHeight: 'auto',
                      overflow: 'visible',
                    }}
                  >
                    {/* TRACK 1: IELTS DEMO WIDGET */}
                    {selectedTrack === 'ielts' && (
                      <div>
                        {/* Segmented Demo Tabs */}
                        <div
                          className="demo-tabs-wrap"
                          style={{
                            display: 'flex',
                            background: 'var(--card-2)',
                            borderRadius: 14,
                            padding: 4,
                            marginBottom: 20,
                            border: '1px solid var(--border)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setDemoTabIelts('writing')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabIelts === 'writing' ? '#38BDF8' : 'transparent',
                              color: demoTabIelts === 'writing' ? '#090d16' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            ✍️ Writing Task 2
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabIelts('speaking')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabIelts === 'speaking' ? '#38BDF8' : 'transparent',
                              color: demoTabIelts === 'speaking' ? '#090d16' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            🎙 AI Speaking
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabIelts('cbt')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabIelts === 'cbt' ? '#38BDF8' : 'transparent',
                              color: demoTabIelts === 'cbt' ? '#090d16' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            🎧 CBT Reading
                          </button>
                        </div>

                        {/* IELTS Tab 1: Writing Task 2 */}
                        {demoTabIelts === 'writing' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--muted)' }}>
                                Academic Writing Task 2
                              </span>
                              <div
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  padding: '4px 12px',
                                  borderRadius: 999,
                                  background: 'rgba(56, 189, 248, 0.15)',
                                  border: '1px solid rgba(56, 189, 248, 0.35)',
                                  color: '#38BDF8',
                                  fontWeight: 800,
                                  fontSize: 13,
                                }}
                              >
                                <span>Overall Band 7.5</span>
                                <span style={{ fontSize: 11, opacity: 0.8 }}>(C1 Proficient)</span>
                              </div>
                            </div>

                            <div
                              style={{
                                padding: 14,
                                borderRadius: 12,
                                background: 'var(--card-2)',
                                border: '1px solid var(--border)',
                                fontSize: 13,
                                color: 'var(--ink-soft)',
                                lineHeight: 1.6,
                                marginBottom: 18,
                              }}
                            >
                              <p style={{ margin: '0 0 8px', fontWeight: 700, color: '#38BDF8' }}>
                                &ldquo;The impact of artificial intelligence on modern employment: positive or negative?&rdquo;
                              </p>
                              <p style={{ margin: 0, fontStyle: 'italic', fontSize: 12 }}>
                                &ldquo;While automation precipitates structural displacement across legacy sectors, it simultaneously spurs high-order cognitive occupations, necessitating state-subsidized reskilling initiatives...&rdquo;
                              </p>
                            </div>

                            <span
                              style={{
                                display: 'block',
                                fontSize: 12,
                                fontWeight: 700,
                                color: 'var(--muted)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                                marginBottom: 10,
                              }}
                            >
                              {t('demo_ielts_criteria_hint')}
                            </span>

                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(2, 1fr)',
                                gap: 8,
                                marginBottom: 16,
                              }}
                            >
                              {IELTS_4_CRITERIA.map((crit) => {
                                const isSelected = selectedCritIelts.id === crit.id;
                                return (
                                  <button
                                    key={crit.id}
                                    type="button"
                                    onClick={() => setSelectedCritIelts(crit)}
                                    style={{
                                      padding: '10px 12px',
                                      borderRadius: 12,
                                      background: isSelected
                                        ? 'rgba(56, 189, 248, 0.18)'
                                        : 'var(--card-2)',
                                      border: isSelected
                                        ? '1px solid #38BDF8'
                                        : '1px solid var(--border)',
                                      textAlign: 'left',
                                      cursor: 'pointer',
                                      transition: 'all 0.18s ease',
                                    }}
                                  >
                                    <div
                                      style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        marginBottom: 4,
                                      }}
                                    >
                                      <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--ink)' }}>
                                        {crit.code}
                                      </span>
                                      <span
                                        style={{
                                          fontSize: 12,
                                          fontWeight: 800,
                                          color: '#38BDF8',
                                        }}
                                      >
                                        Band {crit.band}
                                      </span>
                                    </div>
                                    <div
                                      style={{
                                        fontSize: 11,
                                        color: 'var(--muted)',
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                      }}
                                    >
                                      {crit.name}
                                    </div>
                                  </button>
                                );
                              })}
                            </div>

                            {/* Detail Panel */}
                            <motion.div
                              key={selectedCritIelts.id}
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ duration: 0.18 }}
                              style={{
                                padding: 14,
                                borderRadius: 14,
                                background: 'rgba(56, 189, 248, 0.08)',
                                border: '1px solid rgba(56, 189, 248, 0.25)',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  marginBottom: 6,
                                }}
                              >
                                <span style={{ fontWeight: 800, fontSize: 13, color: 'var(--ink)' }}>
                                  {selectedCritIelts.name}
                                </span>
                                <span
                                  style={{
                                    fontSize: 12,
                                    fontWeight: 800,
                                    padding: '2px 8px',
                                    borderRadius: 6,
                                    background: '#38BDF8',
                                    color: '#090d16',
                                  }}
                                >
                                  {selectedCritIelts.score}
                                </span>
                              </div>
                              <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
                                {selectedCritIelts.desc}
                              </p>
                              <div
                                style={{
                                  fontSize: 12,
                                  color: '#38BDF8',
                                  display: 'flex',
                                  alignItems: 'flex-start',
                                  gap: 6,
                                }}
                              >
                                <span style={{ fontWeight: 800 }}>AI:</span>
                                <span>{selectedCritIelts.feedback}</span>
                              </div>
                            </motion.div>
                          </div>
                        )}

                        {/* IELTS Tab 2: AI Speaking */}
                        {demoTabIelts === 'speaking' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--muted)' }}>
                                {SPEAKING_DEMO.part}
                              </span>
                              <span
                                style={{
                                  padding: '4px 12px',
                                  borderRadius: 999,
                                  background: 'rgba(16, 185, 129, 0.15)',
                                  border: '1px solid rgba(16, 185, 129, 0.35)',
                                  color: '#34D399',
                                  fontWeight: 800,
                                  fontSize: 13,
                                }}
                              >
                                {SPEAKING_DEMO.targetScore}
                              </span>
                            </div>

                            <div
                              style={{
                                padding: 14,
                                borderRadius: 14,
                                background: 'var(--card-2)',
                                border: '1px solid var(--border)',
                                marginBottom: 16,
                              }}
                            >
                              <div style={{ fontSize: 12, fontWeight: 700, color: '#38BDF8', marginBottom: 6 }}>
                                Cue Card Topic:
                              </div>
                              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', marginBottom: 12 }}>
                                {SPEAKING_DEMO.topic}
                              </div>

                              {/* Audio Waveform Simulator */}
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 12,
                                  padding: '12px 16px',
                                  borderRadius: 12,
                                  background: 'rgba(9, 13, 22, 0.6)',
                                  border: '1px solid rgba(56, 189, 248, 0.25)',
                                }}
                              >
                                <button
                                  type="button"
                                  onClick={() => setIsSpeakingPlaying(!isSpeakingPlaying)}
                                  style={{
                                    width: 36,
                                    height: 36,
                                    borderRadius: 999,
                                    background: '#38BDF8',
                                    border: 'none',
                                    color: '#090d16',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer',
                                    boxShadow: '0 2px 10px rgba(56, 189, 248, 0.4)',
                                    flexShrink: 0,
                                  }}
                                >
                                  {isSpeakingPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: 2 }} />}
                                </button>

                                {/* Animated waveform bars */}
                                <div
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 3,
                                    flex: 1,
                                    height: 32,
                                    overflow: 'hidden',
                                  }}
                                >
                                  {[12, 24, 18, 30, 16, 28, 22, 14, 26, 32, 20, 10, 26, 18, 30, 22, 16, 28, 20, 14, 26].map(
                                    (h, i) => (
                                      <div
                                        key={i}
                                        className={`waveform-bar ${isSpeakingPlaying ? 'playing' : ''}`}
                                        style={{
                                          height: isSpeakingPlaying ? undefined : `${h}px`,
                                          animationDelay: `${(i % 5) * 0.12}s`,
                                        }}
                                      />
                                    ),
                                  )}
                                </div>
                                <span style={{ fontSize: 12, fontWeight: 700, color: '#38BDF8' }}>
                                  {isSpeakingPlaying ? '0:24 / 1:45' : '1:45'}
                                </span>
                              </div>
                            </div>

                            {/* Sub-scores */}
                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(4, 1fr)',
                                gap: 8,
                                marginBottom: 14,
                              }}
                            >
                              {[
                                ['Fluency', SPEAKING_DEMO.scores.fluency],
                                ['Pronunciation', SPEAKING_DEMO.scores.pronunciation],
                                ['Lexical', SPEAKING_DEMO.scores.lexical],
                                ['Grammar', SPEAKING_DEMO.scores.grammar],
                              ].map(([label, score]) => (
                                <div
                                  key={label}
                                  style={{
                                    padding: '8px 10px',
                                    borderRadius: 10,
                                    background: 'var(--card-2)',
                                    border: '1px solid var(--border)',
                                    textAlign: 'center',
                                  }}
                                >
                                  <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>
                                    {label}
                                  </div>
                                  <div style={{ fontSize: 14, fontWeight: 900, color: '#38BDF8' }}>
                                    {score}
                                  </div>
                                </div>
                              ))}
                            </div>

                            <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)', lineHeight: 1.5 }}>
                              <span style={{ fontWeight: 800, color: 'var(--ink)' }}>{t('demo_ai_analysis_label')}{' '}</span>
                              {SPEAKING_DEMO.feedback}
                            </p>
                          </div>
                        )}

                        {/* IELTS Tab 3: CBT Reading */}
                        {demoTabIelts === 'cbt' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                {[0, 1, 2].map((idx) => {
                                  const isCurrent = cbtIndexIelts === idx && !cbtFinishedIelts;
                                  const ans = cbtAnswersIelts[idx];
                                  const q = CBT_QUESTIONS_IELTS[idx];
                                  const isCorrect = ans && q.options.find((o) => o.correct)?.key === ans;
                                  let bg = 'var(--card-2)';
                                  let border = '1px solid var(--border)';
                                  let color = 'var(--muted)';
                                  if (ans) {
                                    if (isCorrect) {
                                      bg = 'rgba(16, 185, 129, 0.2)';
                                      border = '1px solid #10B981';
                                      color = '#10B981';
                                    } else {
                                      bg = 'rgba(239, 68, 68, 0.2)';
                                      border = '1px solid #EF4444';
                                      color = '#EF4444';
                                    }
                                  } else if (isCurrent) {
                                    bg = 'rgba(245, 158, 11, 0.2)';
                                    border = '1px solid #38BDF8';
                                    color = '#38BDF8';
                                  }
                                  return (
                                    <button
                                      key={idx}
                                      type="button"
                                      onClick={() => {
                                        setCbtIndexIelts(idx);
                                        setCbtFinishedIelts(false);
                                      }}
                                      style={{
                                        padding: '4px 10px',
                                        borderRadius: 8,
                                        fontSize: 11,
                                        fontWeight: 800,
                                        background: bg,
                                        border,
                                        color,
                                        cursor: 'pointer',
                                        transition: 'all 0.15s ease',
                                      }}
                                    >
                                      {ans ? (isCorrect ? `✓ ${idx + 1}` : `✕ ${idx + 1}`) : `Savol ${idx + 1}`}
                                    </button>
                                  );
                                })}
                              </div>
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 800,
                                  padding: '3px 8px',
                                  borderRadius: 6,
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  color: '#38BDF8',
                                }}
                              >
                                {cbtFinishedIelts ? 'IELTS Reading Natija' : CBT_QUESTIONS_IELTS[cbtIndexIelts].badge}
                              </span>
                            </div>

                            {!cbtFinishedIelts ? (
                              <AnimatePresence mode="wait">
                                <motion.div
                                  key={cbtIndexIelts}
                                  initial={{ opacity: 0, x: 10 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  exit={{ opacity: 0, x: -10 }}
                                  transition={{ duration: 0.18 }}
                                >
                                  {CBT_QUESTIONS_IELTS[cbtIndexIelts].passage && (
                                    <div
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background: 'var(--card-2)',
                                        border: '1px solid var(--border)',
                                        fontSize: 12,
                                        color: 'var(--ink-soft)',
                                        lineHeight: 1.55,
                                        marginBottom: 12,
                                        maxHeight: 90,
                                        overflowY: 'auto',
                                      }}
                                    >
                                      <div
                                        style={{
                                          fontSize: 10,
                                          fontWeight: 800,
                                          textTransform: 'uppercase',
                                          letterSpacing: '0.05em',
                                          color: '#38BDF8',
                                          marginBottom: 4,
                                        }}
                                      >
                                        {CBT_QUESTIONS_IELTS[cbtIndexIelts].passageLabel || 'Matn tahlili'}
                                      </div>
                                      {CBT_QUESTIONS_IELTS[cbtIndexIelts].passage}
                                    </div>
                                  )}

                                  <div
                                    style={{
                                      fontSize: 13,
                                      fontWeight: 700,
                                      color: 'var(--ink)',
                                      lineHeight: 1.5,
                                      marginBottom: 12,
                                    }}
                                  >
                                    {CBT_QUESTIONS_IELTS[cbtIndexIelts].question}
                                  </div>

                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {CBT_QUESTIONS_IELTS[cbtIndexIelts].options.map((opt) => {
                                      const ans = cbtAnswersIelts[cbtIndexIelts];
                                      const isSelected = ans === opt.key;
                                      const isCorrect = !!opt.correct;

                                      let bg = 'var(--card-2)';
                                      let border = '1px solid var(--border)';
                                      let textCol = 'var(--ink)';

                                      if (isSelected) {
                                        if (isCorrect) {
                                          bg = 'rgba(16, 185, 129, 0.18)';
                                          border = '1px solid #10B981';
                                          textCol = '#10B981';
                                        } else {
                                          bg = 'rgba(239, 68, 68, 0.18)';
                                          border = '1px solid #EF4444';
                                          textCol = '#EF4444';
                                        }
                                      } else if (ans && isCorrect) {
                                        bg = 'rgba(16, 185, 129, 0.1)';
                                        border = '1px solid rgba(16, 185, 129, 0.4)';
                                        textCol = '#10B981';
                                      }

                                      return (
                                        <button
                                          key={opt.key}
                                          type="button"
                                          disabled={Boolean(ans)}
                                          onClick={() => handleAnswerQuestion('ielts', cbtIndexIelts, opt.key, isCorrect)}
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 10,
                                            padding: '10px 14px',
                                            borderRadius: 12,
                                            background: bg,
                                            border,
                                            color: textCol,
                                            fontSize: 12,
                                            fontWeight: 600,
                                            textAlign: 'left',
                                            cursor: ans ? 'default' : 'pointer',
                                            transition: 'all 0.18s ease',
                                          }}
                                        >
                                          <span
                                            style={{
                                              width: 22,
                                              height: 22,
                                              borderRadius: 6,
                                              background: isSelected ? 'currentColor' : 'var(--border)',
                                              color: isSelected ? '#090d16' : 'var(--muted)',
                                              fontWeight: 800,
                                              display: 'inline-flex',
                                              alignItems: 'center',
                                              justifyContent: 'center',
                                              fontSize: 11,
                                            }}
                                          >
                                            {opt.key}
                                          </span>
                                          <span>{opt.text}</span>
                                        </button>
                                      );
                                    })}
                                  </div>

                                  {cbtAnswersIelts[cbtIndexIelts] && (
                                    <motion.div
                                      initial={{ opacity: 0, y: 6 }}
                                      animate={{ opacity: 1, y: 0 }}
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background:
                                          CBT_QUESTIONS_IELTS[cbtIndexIelts].options.find(
                                            (o) => o.key === cbtAnswersIelts[cbtIndexIelts]
                                          )?.correct
                                            ? 'rgba(16, 185, 129, 0.1)'
                                            : 'rgba(239, 68, 68, 0.1)',
                                        border:
                                          CBT_QUESTIONS_IELTS[cbtIndexIelts].options.find(
                                            (o) => o.key === cbtAnswersIelts[cbtIndexIelts]
                                          )?.correct
                                            ? '1px solid rgba(16, 185, 129, 0.3)'
                                            : '1px solid rgba(239, 68, 68, 0.3)',
                                        fontSize: 12,
                                        color:
                                          CBT_QUESTIONS_IELTS[cbtIndexIelts].options.find(
                                            (o) => o.key === cbtAnswersIelts[cbtIndexIelts]
                                          )?.correct
                                            ? '#34D399'
                                            : '#F87171',
                                        marginTop: 12,
                                      }}
                                    >
                                      <div style={{ marginBottom: 10 }}>
                                        {CBT_QUESTIONS_IELTS[cbtIndexIelts].explanation}
                                      </div>
                                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                                        {cbtIndexIelts < 2 ? (
                                          <button
                                            type="button"
                                            onClick={() => setCbtIndexIelts((i) => i + 1)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: '#38BDF8',
                                              color: '#090d16',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Keyingi savol ({cbtIndexIelts + 2}/3) →
                                          </button>
                                        ) : (
                                          <button
                                            type="button"
                                            onClick={() => setCbtFinishedIelts(true)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: 'linear-gradient(135deg, #10B981, #059669)',
                                              color: '#FFFFFF',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Natijani ko&apos;rish 🏁
                                          </button>
                                        )}
                                      </div>
                                    </motion.div>
                                  )}
                                </motion.div>
                              </AnimatePresence>
                            ) : (
                              <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.22 }}
                                style={{
                                  padding: '20px 16px',
                                  borderRadius: 16,
                                  background: 'var(--card-2)',
                                  border: '1px solid var(--border)',
                                  textAlign: 'center',
                                }}
                              >
                                {(() => {
                                  const correctCount = [0, 1, 2].filter((i) => {
                                    const a = cbtAnswersIelts[i];
                                    return a && CBT_QUESTIONS_IELTS[i].options.find((o) => o.correct)?.key === a;
                                  }).length;
                                  return (
                                    <>
                                      <div style={{ fontSize: 32, marginBottom: 8 }}>
                                        {correctCount === 3 ? '🏆' : correctCount >= 2 ? '🎉' : '📚'}
                                      </div>
                                      <div
                                        style={{
                                          fontSize: 16,
                                          fontWeight: 800,
                                          color: 'var(--ink)',
                                          marginBottom: 4,
                                        }}
                                      >
                                        Mini CBT Sinovi Yakunlandi!
                                      </div>
                                      <div
                                        style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: 6,
                                          padding: '4px 14px',
                                          borderRadius: 999,
                                          background:
                                            correctCount === 3
                                              ? 'rgba(16, 185, 129, 0.2)'
                                              : 'rgba(245, 158, 11, 0.2)',
                                          color: correctCount === 3 ? '#10B981' : '#F59E0B',
                                          fontSize: 13,
                                          fontWeight: 800,
                                          marginBottom: 12,
                                        }}
                                      >
                                        Natija: {correctCount} / 3 To&apos;g&apos;ri ({Math.round((correctCount / 3) * 100)}%)
                                      </div>
                                      <p
                                        style={{
                                          fontSize: 12,
                                          color: 'var(--ink-soft)',
                                          lineHeight: 1.5,
                                          margin: '0 auto 16px',
                                          maxWidth: 320,
                                        }}
                                      >
                                        {correctCount >= 2
                                          ? "Impressive score! Your performance aligns with Cambridge IELTS Band 7.5+ (C1 Proficient) mastery."
                                          : "Yaxshi boshlanish! Mavzular bo'yicha mustahkamlash mashqlarini bajarish tavsiya etiladi."}
                                      </p>
                                    </>
                                  );
                                })()}

                                <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
                                  <button
                                    type="button"
                                    onClick={() => handleAction('/tests')}
                                    className="btn-glow"
                                    style={{
                                      padding: '10px 18px',
                                      borderRadius: 12,
                                      background: 'linear-gradient(135deg, #38BDF8, #FBBF24)',
                                      color: '#090d16',
                                      fontSize: 12,
                                      fontWeight: 800,
                                      border: 'none',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    To&apos;liq testni boshlash (40 questions) →
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setCbtIndexIelts(0);
                                      setCbtAnswersIelts({});
                                      setCbtFinishedIelts(false);
                                    }}
                                    style={{
                                      padding: '10px 16px',
                                      borderRadius: 12,
                                      background: 'var(--card-2)',
                                      border: '1px solid var(--border)',
                                      color: 'var(--ink)',
                                      fontSize: 12,
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                    }}
                                  >
                                    Qayta ishlash ↺
                                  </button>
                                </div>
                              </motion.div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* TRACK 2: MULTI-LEVEL DEMO WIDGET */}
                    {selectedTrack === 'multilevel' && (
                      <div>
                        {/* Segmented Demo Tabs */}
                        <div
                          className="demo-tabs-wrap"
                          style={{
                            display: 'flex',
                            background: 'var(--card-2)',
                            borderRadius: 14,
                            padding: 4,
                            marginBottom: 20,
                            border: '1px solid var(--border)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setDemoTabMultilevel('writing')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabMultilevel === 'writing' ? '#6366F1' : 'transparent',
                              color: demoTabMultilevel === 'writing' ? '#FFFFFF' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            ✍️ Multi-level Writing
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabMultilevel('cbt')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabMultilevel === 'cbt' ? '#6366F1' : 'transparent',
                              color: demoTabMultilevel === 'cbt' ? '#FFFFFF' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            📚 Reading CBT
                          </button>
                        </div>

                        {/* Multi-level Tab 1: Writing */}
                        {demoTabMultilevel === 'writing' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--muted)' }}>
                                Formal Proposal (Part 2)
                              </span>
                              <div
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  padding: '4px 12px',
                                  borderRadius: 999,
                                  background: 'rgba(99, 102, 241, 0.15)',
                                  border: '1px solid rgba(99, 102, 241, 0.35)',
                                  color: '#818CF8',
                                  fontWeight: 800,
                                  fontSize: 13,
                                }}
                              >
                                <span>Score: 17 / 20</span>
                                <span style={{ fontSize: 11, opacity: 0.8 }}>(C1 Certified)</span>
                              </div>
                            </div>

                            <div
                              style={{
                                padding: 14,
                                borderRadius: 12,
                                background: 'var(--card-2)',
                                border: '1px solid var(--border)',
                                fontSize: 13,
                                color: 'var(--ink-soft)',
                                lineHeight: 1.6,
                                marginBottom: 18,
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                                <span style={{ fontWeight: 700, color: '#818CF8' }}>
                                  Municipal Bike-Sharing System Proposal
                                </span>
                                <span style={{ fontSize: 11, color: '#10B981', fontWeight: 700 }}>
                                  184 words (Optimal)
                                </span>
                              </div>
                              <p style={{ margin: 0, fontStyle: 'italic', fontSize: 12 }}>
                                &ldquo;To mitigate persistent rush-hour bottlenecks across the city center, I urge the council to inaugurate a docked bicycle-sharing network, subsidizing initial infrastructural outlays...&rdquo;
                              </p>
                            </div>

                            <span
                              style={{
                                display: 'block',
                                fontSize: 12,
                                fontWeight: 700,
                                color: 'var(--muted)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                                marginBottom: 10,
                              }}
                            >
                              {t('demo_multi_criteria_hint')}
                            </span>

                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(2, 1fr)',
                                gap: 8,
                                marginBottom: 16,
                              }}
                            >
                              {MULTILEVEL_4_CRITERIA.map((crit) => {
                                const isSelected = selectedCritMultilevel.id === crit.id;
                                return (
                                  <button
                                    key={crit.id}
                                    type="button"
                                    onClick={() => setSelectedCritMultilevel(crit)}
                                    style={{
                                      padding: '10px 12px',
                                      borderRadius: 12,
                                      background: isSelected
                                        ? 'rgba(99, 102, 241, 0.18)'
                                        : 'var(--card-2)',
                                      border: isSelected
                                        ? '1px solid #6366F1'
                                        : '1px solid var(--border)',
                                      textAlign: 'left',
                                      cursor: 'pointer',
                                      transition: 'all 0.18s ease',
                                    }}
                                  >
                                    <div
                                      style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        marginBottom: 4,
                                      }}
                                    >
                                      <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--ink)' }}>
                                        {crit.code}
                                      </span>
                                      <span style={{ fontSize: 12, fontWeight: 800, color: '#818CF8' }}>
                                        {crit.score}
                                      </span>
                                    </div>
                                    <div
                                      style={{
                                        fontSize: 11,
                                        color: 'var(--muted)',
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                      }}
                                    >
                                      {crit.name}
                                    </div>
                                  </button>
                                );
                              })}
                            </div>

                            {/* Detail Panel */}
                            <motion.div
                              key={selectedCritMultilevel.id}
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ duration: 0.18 }}
                              style={{
                                padding: 14,
                                borderRadius: 14,
                                background: 'rgba(99, 102, 241, 0.08)',
                                border: '1px solid rgba(99, 102, 241, 0.25)',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  marginBottom: 6,
                                }}
                              >
                                <span style={{ fontWeight: 800, fontSize: 13, color: 'var(--ink)' }}>
                                  {selectedCritMultilevel.name}
                                </span>
                                <span
                                  style={{
                                    fontSize: 12,
                                    fontWeight: 800,
                                    padding: '2px 8px',
                                    borderRadius: 6,
                                    background: '#6366F1',
                                    color: '#FFFFFF',
                                  }}
                                >
                                  {selectedCritMultilevel.score}
                                </span>
                              </div>
                              <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
                                {selectedCritMultilevel.desc}
                              </p>
                              <div
                                style={{
                                  fontSize: 12,
                                  color: '#818CF8',
                                  display: 'flex',
                                  alignItems: 'flex-start',
                                  gap: 6,
                                }}
                              >
                                <span style={{ fontWeight: 800 }}>AI:</span>
                                <span>{selectedCritMultilevel.feedback}</span>
                              </div>
                            </motion.div>
                          </div>
                        )}

                        {/* Multi-level Tab 2: Reading CBT */}
                        {demoTabMultilevel === 'cbt' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                {[0, 1, 2].map((idx) => {
                                  const isCurrent = cbtIndexMultilevel === idx && !cbtFinishedMultilevel;
                                  const ans = cbtAnswersMultilevel[idx];
                                  const q = CBT_QUESTIONS_MULTILEVEL[idx];
                                  const isCorrect = ans && q.options.find((o) => o.correct)?.key === ans;
                                  let bg = 'var(--card-2)';
                                  let border = '1px solid var(--border)';
                                  let color = 'var(--muted)';
                                  if (ans) {
                                    if (isCorrect) {
                                      bg = 'rgba(16, 185, 129, 0.2)';
                                      border = '1px solid #10B981';
                                      color = '#10B981';
                                    } else {
                                      bg = 'rgba(239, 68, 68, 0.2)';
                                      border = '1px solid #EF4444';
                                      color = '#EF4444';
                                    }
                                  } else if (isCurrent) {
                                    bg = 'rgba(245, 158, 11, 0.2)';
                                    border = '1px solid #6366F1';
                                    color = '#6366F1';
                                  }
                                  return (
                                    <button
                                      key={idx}
                                      type="button"
                                      onClick={() => {
                                        setCbtIndexMultilevel(idx);
                                        setCbtFinishedMultilevel(false);
                                      }}
                                      style={{
                                        padding: '4px 10px',
                                        borderRadius: 8,
                                        fontSize: 11,
                                        fontWeight: 800,
                                        background: bg,
                                        border,
                                        color,
                                        cursor: 'pointer',
                                        transition: 'all 0.15s ease',
                                      }}
                                    >
                                      {ans ? (isCorrect ? `✓ ${idx + 1}` : `✕ ${idx + 1}`) : `Savol ${idx + 1}`}
                                    </button>
                                  );
                                })}
                              </div>
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 800,
                                  padding: '3px 8px',
                                  borderRadius: 6,
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  color: '#6366F1',
                                }}
                              >
                                {cbtFinishedMultilevel ? 'CEFR B2/C1 Natija' : CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].badge}
                              </span>
                            </div>

                            {!cbtFinishedMultilevel ? (
                              <AnimatePresence mode="wait">
                                <motion.div
                                  key={cbtIndexMultilevel}
                                  initial={{ opacity: 0, x: 10 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  exit={{ opacity: 0, x: -10 }}
                                  transition={{ duration: 0.18 }}
                                >
                                  {CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].passage && (
                                    <div
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background: 'var(--card-2)',
                                        border: '1px solid var(--border)',
                                        fontSize: 12,
                                        color: 'var(--ink-soft)',
                                        lineHeight: 1.55,
                                        marginBottom: 12,
                                        maxHeight: 90,
                                        overflowY: 'auto',
                                      }}
                                    >
                                      <div
                                        style={{
                                          fontSize: 10,
                                          fontWeight: 800,
                                          textTransform: 'uppercase',
                                          letterSpacing: '0.05em',
                                          color: '#6366F1',
                                          marginBottom: 4,
                                        }}
                                      >
                                        {CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].passageLabel || 'Matn tahlili'}
                                      </div>
                                      {CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].passage}
                                    </div>
                                  )}

                                  <div
                                    style={{
                                      fontSize: 13,
                                      fontWeight: 700,
                                      color: 'var(--ink)',
                                      lineHeight: 1.5,
                                      marginBottom: 12,
                                    }}
                                  >
                                    {CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].question}
                                  </div>

                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].options.map((opt) => {
                                      const ans = cbtAnswersMultilevel[cbtIndexMultilevel];
                                      const isSelected = ans === opt.key;
                                      const isCorrect = !!opt.correct;

                                      let bg = 'var(--card-2)';
                                      let border = '1px solid var(--border)';
                                      let textCol = 'var(--ink)';

                                      if (isSelected) {
                                        if (isCorrect) {
                                          bg = 'rgba(16, 185, 129, 0.18)';
                                          border = '1px solid #10B981';
                                          textCol = '#10B981';
                                        } else {
                                          bg = 'rgba(239, 68, 68, 0.18)';
                                          border = '1px solid #EF4444';
                                          textCol = '#EF4444';
                                        }
                                      } else if (ans && isCorrect) {
                                        bg = 'rgba(16, 185, 129, 0.1)';
                                        border = '1px solid rgba(16, 185, 129, 0.4)';
                                        textCol = '#10B981';
                                      }

                                      return (
                                        <button
                                          key={opt.key}
                                          type="button"
                                          disabled={Boolean(ans)}
                                          onClick={() => handleAnswerQuestion('multi', cbtIndexMultilevel, opt.key, isCorrect)}
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 10,
                                            padding: '10px 14px',
                                            borderRadius: 12,
                                            background: bg,
                                            border,
                                            color: textCol,
                                            fontSize: 12,
                                            fontWeight: 600,
                                            textAlign: 'left',
                                            cursor: ans ? 'default' : 'pointer',
                                            transition: 'all 0.18s ease',
                                          }}
                                        >
                                          <span
                                            style={{
                                              width: 22,
                                              height: 22,
                                              borderRadius: 6,
                                              background: isSelected ? 'currentColor' : 'var(--border)',
                                              color: isSelected ? '#090d16' : 'var(--muted)',
                                              fontWeight: 800,
                                              display: 'inline-flex',
                                              alignItems: 'center',
                                              justifyContent: 'center',
                                              fontSize: 11,
                                            }}
                                          >
                                            {opt.key}
                                          </span>
                                          <span>{opt.text}</span>
                                        </button>
                                      );
                                    })}
                                  </div>

                                  {cbtAnswersMultilevel[cbtIndexMultilevel] && (
                                    <motion.div
                                      initial={{ opacity: 0, y: 6 }}
                                      animate={{ opacity: 1, y: 0 }}
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background:
                                          CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].options.find(
                                            (o) => o.key === cbtAnswersMultilevel[cbtIndexMultilevel]
                                          )?.correct
                                            ? 'rgba(16, 185, 129, 0.1)'
                                            : 'rgba(239, 68, 68, 0.1)',
                                        border:
                                          CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].options.find(
                                            (o) => o.key === cbtAnswersMultilevel[cbtIndexMultilevel]
                                          )?.correct
                                            ? '1px solid rgba(16, 185, 129, 0.3)'
                                            : '1px solid rgba(239, 68, 68, 0.3)',
                                        fontSize: 12,
                                        color:
                                          CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].options.find(
                                            (o) => o.key === cbtAnswersMultilevel[cbtIndexMultilevel]
                                          )?.correct
                                            ? '#34D399'
                                            : '#F87171',
                                        marginTop: 12,
                                      }}
                                    >
                                      <div style={{ marginBottom: 10 }}>
                                        {CBT_QUESTIONS_MULTILEVEL[cbtIndexMultilevel].explanation}
                                      </div>
                                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                                        {cbtIndexMultilevel < 2 ? (
                                          <button
                                            type="button"
                                            onClick={() => setCbtIndexMultilevel((i) => i + 1)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: '#6366F1',
                                              color: '#090d16',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Keyingi savol ({cbtIndexMultilevel + 2}/3) →
                                          </button>
                                        ) : (
                                          <button
                                            type="button"
                                            onClick={() => setCbtFinishedMultilevel(true)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: 'linear-gradient(135deg, #10B981, #059669)',
                                              color: '#FFFFFF',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Natijani ko&apos;rish 🏁
                                          </button>
                                        )}
                                      </div>
                                    </motion.div>
                                  )}
                                </motion.div>
                              </AnimatePresence>
                            ) : (
                              <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.22 }}
                                style={{
                                  padding: '20px 16px',
                                  borderRadius: 16,
                                  background: 'var(--card-2)',
                                  border: '1px solid var(--border)',
                                  textAlign: 'center',
                                }}
                              >
                                {(() => {
                                  const correctCount = [0, 1, 2].filter((i) => {
                                    const a = cbtAnswersMultilevel[i];
                                    return a && CBT_QUESTIONS_MULTILEVEL[i].options.find((o) => o.correct)?.key === a;
                                  }).length;
                                  return (
                                    <>
                                      <div style={{ fontSize: 32, marginBottom: 8 }}>
                                        {correctCount === 3 ? '🏆' : correctCount >= 2 ? '🎉' : '📚'}
                                      </div>
                                      <div
                                        style={{
                                          fontSize: 16,
                                          fontWeight: 800,
                                          color: 'var(--ink)',
                                          marginBottom: 4,
                                        }}
                                      >
                                        Mini CBT Sinovi Yakunlandi!
                                      </div>
                                      <div
                                        style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: 6,
                                          padding: '4px 14px',
                                          borderRadius: 999,
                                          background:
                                            correctCount === 3
                                              ? 'rgba(16, 185, 129, 0.2)'
                                              : 'rgba(245, 158, 11, 0.2)',
                                          color: correctCount === 3 ? '#10B981' : '#F59E0B',
                                          fontSize: 13,
                                          fontWeight: 800,
                                          marginBottom: 12,
                                        }}
                                      >
                                        Natija: {correctCount} / 3 To&apos;g&apos;ri ({Math.round((correctCount / 3) * 100)}%)
                                      </div>
                                      <p
                                        style={{
                                          fontSize: 12,
                                          color: 'var(--ink-soft)',
                                          lineHeight: 1.5,
                                          margin: '0 auto 16px',
                                          maxWidth: 320,
                                        }}
                                      >
                                        {correctCount >= 2
                                          ? "Ajoyib natija! DTM/BMB CEFR Multi-level imtihoni bo'yicha C1 sertifikati olish darajasiga munosib natija."
                                          : "Yaxshi boshlanish! Mavzular bo'yicha mustahkamlash mashqlarini bajarish tavsiya etiladi."}
                                      </p>
                                    </>
                                  );
                                })()}

                                <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
                                  <button
                                    type="button"
                                    onClick={() => handleAction('/tests')}
                                    className="btn-glow"
                                    style={{
                                      padding: '10px 18px',
                                      borderRadius: 12,
                                      background: 'linear-gradient(135deg, #6366F1, #FBBF24)',
                                      color: '#090d16',
                                      fontSize: 12,
                                      fontWeight: 800,
                                      border: 'none',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    To&apos;liq testni boshlash (35 ta savol) →
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setCbtIndexMultilevel(0);
                                      setCbtAnswersMultilevel({});
                                      setCbtFinishedMultilevel(false);
                                    }}
                                    style={{
                                      padding: '10px 16px',
                                      borderRadius: 12,
                                      background: 'var(--card-2)',
                                      border: '1px solid var(--border)',
                                      color: 'var(--ink)',
                                      fontSize: 12,
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                    }}
                                  >
                                    Qayta ishlash ↺
                                  </button>
                                </div>
                              </motion.div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* TRACK 3: NATIONAL CERTIFICATE DEMO WIDGET */}
                    {selectedTrack === 'national_certificate' && (
                      <div>
                        {/* Segmented Demo Tabs */}
                        <div
                          className="demo-tabs-wrap"
                          style={{
                            display: 'flex',
                            background: 'var(--card-2)',
                            borderRadius: 14,
                            padding: 4,
                            marginBottom: 20,
                            border: '1px solid var(--border)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setDemoTabNatCert('essay')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabNatCert === 'essay' ? '#F59E0B' : 'transparent',
                              color: demoTabNatCert === 'essay' ? '#090d16' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            ✍️ AI Esse (12 Mezon)
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabNatCert('test')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabNatCert === 'test' ? '#F59E0B' : 'transparent',
                              color: demoTabNatCert === 'test' ? '#090d16' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            📚 Fast CBT Test
                          </button>
                        </div>

                        {/* NatCert Tab 1: 12 Mezonli Esse */}
                        {demoTabNatCert === 'essay' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--muted)' }}>
                                Alisher Navoiy &apos;Xamsa&apos;si tahlili
                              </span>
                              <div
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  padding: '4px 12px',
                                  borderRadius: 999,
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  border: '1px solid rgba(245, 158, 11, 0.35)',
                                  color: '#F59E0B',
                                  fontWeight: 800,
                                  fontSize: 13,
                                }}
                              >
                                <span>54.5 / 60 ball</span>
                                <span style={{ fontSize: 11, opacity: 0.8 }}>(A daraja - 90.8%)</span>
                              </div>
                            </div>

                            <span
                              style={{
                                display: 'block',
                                fontSize: 12,
                                fontWeight: 700,
                                color: 'var(--muted)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                                marginBottom: 10,
                              }}
                            >
                              12 ta rasmiy BMB mezonlari (Bosib ko&apos;ring):
                            </span>

                            <div
                              className="cbt-crit-grid"
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(6, 1fr)',
                                gap: 5,
                                marginBottom: 12,
                              }}
                            >
                              {ESSAY_12_CRITERIA.map((crit) => {
                                const isSelected = selectedCritNatCert.id === crit.id;
                                return (
                                  <button
                                    key={crit.id}
                                    type="button"
                                    onClick={() => setSelectedCritNatCert(crit)}
                                    style={{
                                      padding: '8px 4px',
                                      borderRadius: 10,
                                      background: isSelected
                                        ? 'rgba(245, 158, 11, 0.2)'
                                        : 'var(--card-2)',
                                      border: isSelected
                                        ? '1px solid #F59E0B'
                                        : '1px solid var(--border)',
                                      textAlign: 'center',
                                      cursor: 'pointer',
                                      transition: 'all 0.18s ease',
                                    }}
                                  >
                                    <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--ink)' }}>
                                      #{crit.id}
                                    </div>
                                    <div
                                      style={{
                                        fontSize: 11,
                                        fontWeight: 800,
                                        color: crit.percent >= 90 ? '#10B981' : '#F59E0B',
                                      }}
                                    >
                                      {crit.score.split(' ')[0]}
                                    </div>
                                  </button>
                                );
                              })}
                            </div>

                            {/* Detail Panel */}
                            <motion.div
                              key={selectedCritNatCert.id}
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ duration: 0.18 }}
                              style={{
                                padding: '12px 14px',
                                minHeight: 110,
                                borderRadius: 14,
                                background: 'rgba(245, 158, 11, 0.08)',
                                border: '1px solid rgba(245, 158, 11, 0.25)',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  marginBottom: 6,
                                }}
                              >
                                <span style={{ fontWeight: 800, fontSize: 13, color: 'var(--ink)' }}>
                                  #{selectedCritNatCert.id}. {selectedCritNatCert.name}
                                </span>
                                <span
                                  style={{
                                    fontSize: 12,
                                    fontWeight: 800,
                                    padding: '2px 8px',
                                    borderRadius: 6,
                                    background: '#F59E0B',
                                    color: '#090d16',
                                  }}
                                >
                                  {selectedCritNatCert.score}
                                </span>
                              </div>
                              <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
                                {selectedCritNatCert.desc}
                              </p>
                              <div
                                style={{
                                  fontSize: 12,
                                  color: '#F59E0B',
                                  display: 'flex',
                                  alignItems: 'flex-start',
                                  gap: 6,
                                }}
                              >
                                <span style={{ fontWeight: 800 }}>Tavsiya:</span>
                                <span>{selectedCritNatCert.advice}</span>
                              </div>
                            </motion.div>
                          </div>
                        )}

                        {/* NatCert Tab 2: Fast CBT Test */}
                        {demoTabNatCert === 'test' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                {[0, 1, 2].map((idx) => {
                                  const isCurrent = cbtIndexNatCert === idx && !cbtFinishedNatCert;
                                  const ans = cbtAnswersNatCert[idx];
                                  const q = CBT_QUESTIONS_UZBEK[idx];
                                  const isCorrect = ans && q.options.find((o) => o.correct)?.key === ans;
                                  let bg = 'var(--card-2)';
                                  let border = '1px solid var(--border)';
                                  let color = 'var(--muted)';
                                  if (ans) {
                                    if (isCorrect) {
                                      bg = 'rgba(16, 185, 129, 0.2)';
                                      border = '1px solid #10B981';
                                      color = '#10B981';
                                    } else {
                                      bg = 'rgba(239, 68, 68, 0.2)';
                                      border = '1px solid #EF4444';
                                      color = '#EF4444';
                                    }
                                  } else if (isCurrent) {
                                    bg = 'rgba(245, 158, 11, 0.2)';
                                    border = '1px solid #F59E0B';
                                    color = '#F59E0B';
                                  }
                                  return (
                                    <button
                                      key={idx}
                                      type="button"
                                      onClick={() => {
                                        setCbtIndexNatCert(idx);
                                        setCbtFinishedNatCert(false);
                                      }}
                                      style={{
                                        padding: '4px 10px',
                                        borderRadius: 8,
                                        fontSize: 11,
                                        fontWeight: 800,
                                        background: bg,
                                        border,
                                        color,
                                        cursor: 'pointer',
                                        transition: 'all 0.15s ease',
                                      }}
                                    >
                                      {ans ? (isCorrect ? `✓ ${idx + 1}` : `✕ ${idx + 1}`) : `Savol ${idx + 1}`}
                                    </button>
                                  );
                                })}
                              </div>
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 800,
                                  padding: '3px 8px',
                                  borderRadius: 6,
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  color: '#F59E0B',
                                }}
                              >
                                {cbtFinishedNatCert ? 'BMB 2026 Natija' : CBT_QUESTIONS_UZBEK[cbtIndexNatCert].badge}
                              </span>
                            </div>

                            {!cbtFinishedNatCert ? (
                              <AnimatePresence mode="wait">
                                <motion.div
                                  key={cbtIndexNatCert}
                                  initial={{ opacity: 0, x: 10 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  exit={{ opacity: 0, x: -10 }}
                                  transition={{ duration: 0.18 }}
                                >
                                  {CBT_QUESTIONS_UZBEK[cbtIndexNatCert].passage && (
                                    <div
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background: 'var(--card-2)',
                                        border: '1px solid var(--border)',
                                        fontSize: 12,
                                        color: 'var(--ink-soft)',
                                        lineHeight: 1.55,
                                        marginBottom: 12,
                                        maxHeight: 90,
                                        overflowY: 'auto',
                                      }}
                                    >
                                      <div
                                        style={{
                                          fontSize: 10,
                                          fontWeight: 800,
                                          textTransform: 'uppercase',
                                          letterSpacing: '0.05em',
                                          color: '#F59E0B',
                                          marginBottom: 4,
                                        }}
                                      >
                                        {CBT_QUESTIONS_UZBEK[cbtIndexNatCert].passageLabel || 'Matn tahlili'}
                                      </div>
                                      {CBT_QUESTIONS_UZBEK[cbtIndexNatCert].passage}
                                    </div>
                                  )}

                                  <div
                                    style={{
                                      fontSize: 13,
                                      fontWeight: 700,
                                      color: 'var(--ink)',
                                      lineHeight: 1.5,
                                      marginBottom: 12,
                                    }}
                                  >
                                    {CBT_QUESTIONS_UZBEK[cbtIndexNatCert].question}
                                  </div>

                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {CBT_QUESTIONS_UZBEK[cbtIndexNatCert].options.map((opt) => {
                                      const ans = cbtAnswersNatCert[cbtIndexNatCert];
                                      const isSelected = ans === opt.key;
                                      const isCorrect = !!opt.correct;

                                      let bg = 'var(--card-2)';
                                      let border = '1px solid var(--border)';
                                      let textCol = 'var(--ink)';

                                      if (isSelected) {
                                        if (isCorrect) {
                                          bg = 'rgba(16, 185, 129, 0.18)';
                                          border = '1px solid #10B981';
                                          textCol = '#10B981';
                                        } else {
                                          bg = 'rgba(239, 68, 68, 0.18)';
                                          border = '1px solid #EF4444';
                                          textCol = '#EF4444';
                                        }
                                      } else if (ans && isCorrect) {
                                        bg = 'rgba(16, 185, 129, 0.1)';
                                        border = '1px solid rgba(16, 185, 129, 0.4)';
                                        textCol = '#10B981';
                                      }

                                      return (
                                        <button
                                          key={opt.key}
                                          type="button"
                                          disabled={Boolean(ans)}
                                          onClick={() => handleAnswerQuestion('nat', cbtIndexNatCert, opt.key, isCorrect)}
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 10,
                                            padding: '10px 14px',
                                            borderRadius: 12,
                                            background: bg,
                                            border,
                                            color: textCol,
                                            fontSize: 12,
                                            fontWeight: 600,
                                            textAlign: 'left',
                                            cursor: ans ? 'default' : 'pointer',
                                            transition: 'all 0.18s ease',
                                          }}
                                        >
                                          <span
                                            style={{
                                              width: 22,
                                              height: 22,
                                              borderRadius: 6,
                                              background: isSelected ? 'currentColor' : 'var(--border)',
                                              color: isSelected ? '#090d16' : 'var(--muted)',
                                              fontWeight: 800,
                                              display: 'inline-flex',
                                              alignItems: 'center',
                                              justifyContent: 'center',
                                              fontSize: 11,
                                            }}
                                          >
                                            {opt.key}
                                          </span>
                                          <span>{opt.text}</span>
                                        </button>
                                      );
                                    })}
                                  </div>

                                  {cbtAnswersNatCert[cbtIndexNatCert] && (
                                    <motion.div
                                      initial={{ opacity: 0, y: 6 }}
                                      animate={{ opacity: 1, y: 0 }}
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background:
                                          CBT_QUESTIONS_UZBEK[cbtIndexNatCert].options.find(
                                            (o) => o.key === cbtAnswersNatCert[cbtIndexNatCert]
                                          )?.correct
                                            ? 'rgba(16, 185, 129, 0.1)'
                                            : 'rgba(239, 68, 68, 0.1)',
                                        border:
                                          CBT_QUESTIONS_UZBEK[cbtIndexNatCert].options.find(
                                            (o) => o.key === cbtAnswersNatCert[cbtIndexNatCert]
                                          )?.correct
                                            ? '1px solid rgba(16, 185, 129, 0.3)'
                                            : '1px solid rgba(239, 68, 68, 0.3)',
                                        fontSize: 12,
                                        color:
                                          CBT_QUESTIONS_UZBEK[cbtIndexNatCert].options.find(
                                            (o) => o.key === cbtAnswersNatCert[cbtIndexNatCert]
                                          )?.correct
                                            ? '#34D399'
                                            : '#F87171',
                                        marginTop: 12,
                                      }}
                                    >
                                      <div style={{ marginBottom: 10 }}>
                                        {CBT_QUESTIONS_UZBEK[cbtIndexNatCert].explanation}
                                      </div>
                                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                                        {cbtIndexNatCert < 2 ? (
                                          <button
                                            type="button"
                                            onClick={() => setCbtIndexNatCert((i) => i + 1)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: '#F59E0B',
                                              color: '#090d16',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Keyingi savol ({cbtIndexNatCert + 2}/3) →
                                          </button>
                                        ) : (
                                          <button
                                            type="button"
                                            onClick={() => setCbtFinishedNatCert(true)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: 'linear-gradient(135deg, #10B981, #059669)',
                                              color: '#FFFFFF',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Natijani ko&apos;rish 🏁
                                          </button>
                                        )}
                                      </div>
                                    </motion.div>
                                  )}
                                </motion.div>
                              </AnimatePresence>
                            ) : (
                              <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.22 }}
                                style={{
                                  padding: '20px 16px',
                                  borderRadius: 16,
                                  background: 'var(--card-2)',
                                  border: '1px solid var(--border)',
                                  textAlign: 'center',
                                }}
                              >
                                {(() => {
                                  const correctCount = [0, 1, 2].filter((i) => {
                                    const a = cbtAnswersNatCert[i];
                                    return a && CBT_QUESTIONS_UZBEK[i].options.find((o) => o.correct)?.key === a;
                                  }).length;
                                  return (
                                    <>
                                      <div style={{ fontSize: 32, marginBottom: 8 }}>
                                        {correctCount === 3 ? '🏆' : correctCount >= 2 ? '🎉' : '📚'}
                                      </div>
                                      <div
                                        style={{
                                          fontSize: 16,
                                          fontWeight: 800,
                                          color: 'var(--ink)',
                                          marginBottom: 4,
                                        }}
                                      >
                                        Mini CBT Sinovi Yakunlandi!
                                      </div>
                                      <div
                                        style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: 6,
                                          padding: '4px 14px',
                                          borderRadius: 999,
                                          background:
                                            correctCount === 3
                                              ? 'rgba(16, 185, 129, 0.2)'
                                              : 'rgba(245, 158, 11, 0.2)',
                                          color: correctCount === 3 ? '#10B981' : '#F59E0B',
                                          fontSize: 13,
                                          fontWeight: 800,
                                          marginBottom: 12,
                                        }}
                                      >
                                        Natija: {correctCount} / 3 To&apos;g&apos;ri ({Math.round((correctCount / 3) * 100)}%)
                                      </div>
                                      <p
                                        style={{
                                          fontSize: 12,
                                          color: 'var(--ink-soft)',
                                          lineHeight: 1.5,
                                          margin: '0 auto 16px',
                                          maxWidth: 320,
                                        }}
                                      >
                                        {correctCount >= 2
                                          ? "Ajoyib natija! Sizda BMB Milliy Sertifikatining A/A+ darajasini qo'lga kiritish salohiyati juda yuqori."
                                          : "Yaxshi boshlanish! Mavzular bo'yicha mustahkamlash mashqlarini bajarish tavsiya etiladi."}
                                      </p>
                                    </>
                                  );
                                })()}

                                <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
                                  <button
                                    type="button"
                                    onClick={() => handleAction('/tests')}
                                    className="btn-glow"
                                    style={{
                                      padding: '10px 18px',
                                      borderRadius: 12,
                                      background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                                      color: '#090d16',
                                      fontSize: 12,
                                      fontWeight: 800,
                                      border: 'none',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    To&apos;liq testni boshlash (45 ta savol) →
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setCbtIndexNatCert(0);
                                      setCbtAnswersNatCert({});
                                      setCbtFinishedNatCert(false);
                                    }}
                                    style={{
                                      padding: '10px 16px',
                                      borderRadius: 12,
                                      background: 'var(--card-2)',
                                      border: '1px solid var(--border)',
                                      color: 'var(--ink)',
                                      fontSize: 12,
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                    }}
                                  >
                                    Qayta ishlash ↺
                                  </button>
                                </div>
                              </motion.div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* TRACK 4: ATTESTATION DEMO WIDGET */}
                    {selectedTrack === 'attestation' && (
                      <div>
                        {/* Segmented Demo Tabs */}
                        <div
                          className="demo-tabs-wrap"
                          style={{
                            display: 'flex',
                            background: 'var(--card-2)',
                            borderRadius: 14,
                            padding: 4,
                            marginBottom: 20,
                            border: '1px solid var(--border)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setDemoTabAttestation('test')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabAttestation === 'test' ? '#F59E0B' : 'transparent',
                              color: demoTabAttestation === 'test' ? '#090d16' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            👨‍🏫 Attestatsiya Testi
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabAttestation('diagnostic')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: 'none',
                              background: demoTabAttestation === 'diagnostic' ? '#F59E0B' : 'transparent',
                              color: demoTabAttestation === 'diagnostic' ? '#090d16' : 'var(--muted)',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            📊 Toifa Diagnostikasi
                          </button>
                        </div>

                        {/* Attestation Tab 1: Test Savoli */}
                        {demoTabAttestation === 'test' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                {[0, 1, 2].map((idx) => {
                                  const isCurrent = cbtIndexAttestation === idx && !cbtFinishedAttestation;
                                  const ans = cbtAnswersAttestation[idx];
                                  const q = CBT_QUESTIONS_ATTESTATION[idx];
                                  const isCorrect = ans && q.options.find((o) => o.correct)?.key === ans;
                                  let bg = 'var(--card-2)';
                                  let border = '1px solid var(--border)';
                                  let color = 'var(--muted)';
                                  if (ans) {
                                    if (isCorrect) {
                                      bg = 'rgba(16, 185, 129, 0.2)';
                                      border = '1px solid #10B981';
                                      color = '#10B981';
                                    } else {
                                      bg = 'rgba(239, 68, 68, 0.2)';
                                      border = '1px solid #EF4444';
                                      color = '#EF4444';
                                    }
                                  } else if (isCurrent) {
                                    bg = 'rgba(245, 158, 11, 0.2)';
                                    border = '1px solid #F59E0B';
                                    color = '#F59E0B';
                                  }
                                  return (
                                    <button
                                      key={idx}
                                      type="button"
                                      onClick={() => {
                                        setCbtIndexAttestation(idx);
                                        setCbtFinishedAttestation(false);
                                      }}
                                      style={{
                                        padding: '4px 10px',
                                        borderRadius: 8,
                                        fontSize: 11,
                                        fontWeight: 800,
                                        background: bg,
                                        border,
                                        color,
                                        cursor: 'pointer',
                                        transition: 'all 0.15s ease',
                                      }}
                                    >
                                      {ans ? (isCorrect ? `✓ ${idx + 1}` : `✕ ${idx + 1}`) : `Savol ${idx + 1}`}
                                    </button>
                                  );
                                })}
                              </div>
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 800,
                                  padding: '3px 8px',
                                  borderRadius: 6,
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  color: '#F59E0B',
                                }}
                              >
                                {cbtFinishedAttestation ? 'Attestatsiya 2026 Natija' : CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].badge}
                              </span>
                            </div>

                            {!cbtFinishedAttestation ? (
                              <AnimatePresence mode="wait">
                                <motion.div
                                  key={cbtIndexAttestation}
                                  initial={{ opacity: 0, x: 10 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  exit={{ opacity: 0, x: -10 }}
                                  transition={{ duration: 0.18 }}
                                >
                                  {CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].passage && (
                                    <div
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background: 'var(--card-2)',
                                        border: '1px solid var(--border)',
                                        fontSize: 12,
                                        color: 'var(--ink-soft)',
                                        lineHeight: 1.55,
                                        marginBottom: 12,
                                        maxHeight: 90,
                                        overflowY: 'auto',
                                      }}
                                    >
                                      <div
                                        style={{
                                          fontSize: 10,
                                          fontWeight: 800,
                                          textTransform: 'uppercase',
                                          letterSpacing: '0.05em',
                                          color: '#F59E0B',
                                          marginBottom: 4,
                                        }}
                                      >
                                        {CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].passageLabel || 'Matn tahlili'}
                                      </div>
                                      {CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].passage}
                                    </div>
                                  )}

                                  <div
                                    style={{
                                      fontSize: 13,
                                      fontWeight: 700,
                                      color: 'var(--ink)',
                                      lineHeight: 1.5,
                                      marginBottom: 12,
                                    }}
                                  >
                                    {CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].question}
                                  </div>

                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].options.map((opt) => {
                                      const ans = cbtAnswersAttestation[cbtIndexAttestation];
                                      const isSelected = ans === opt.key;
                                      const isCorrect = !!opt.correct;

                                      let bg = 'var(--card-2)';
                                      let border = '1px solid var(--border)';
                                      let textCol = 'var(--ink)';

                                      if (isSelected) {
                                        if (isCorrect) {
                                          bg = 'rgba(16, 185, 129, 0.18)';
                                          border = '1px solid #10B981';
                                          textCol = '#10B981';
                                        } else {
                                          bg = 'rgba(239, 68, 68, 0.18)';
                                          border = '1px solid #EF4444';
                                          textCol = '#EF4444';
                                        }
                                      } else if (ans && isCorrect) {
                                        bg = 'rgba(16, 185, 129, 0.1)';
                                        border = '1px solid rgba(16, 185, 129, 0.4)';
                                        textCol = '#10B981';
                                      }

                                      return (
                                        <button
                                          key={opt.key}
                                          type="button"
                                          disabled={Boolean(ans)}
                                          onClick={() => handleAnswerQuestion('attest', cbtIndexAttestation, opt.key, isCorrect)}
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 10,
                                            padding: '10px 14px',
                                            borderRadius: 12,
                                            background: bg,
                                            border,
                                            color: textCol,
                                            fontSize: 12,
                                            fontWeight: 600,
                                            textAlign: 'left',
                                            cursor: ans ? 'default' : 'pointer',
                                            transition: 'all 0.18s ease',
                                          }}
                                        >
                                          <span
                                            style={{
                                              width: 22,
                                              height: 22,
                                              borderRadius: 6,
                                              background: isSelected ? 'currentColor' : 'var(--border)',
                                              color: isSelected ? '#090d16' : 'var(--muted)',
                                              fontWeight: 800,
                                              display: 'inline-flex',
                                              alignItems: 'center',
                                              justifyContent: 'center',
                                              fontSize: 11,
                                            }}
                                          >
                                            {opt.key}
                                          </span>
                                          <span>{opt.text}</span>
                                        </button>
                                      );
                                    })}
                                  </div>

                                  {cbtAnswersAttestation[cbtIndexAttestation] && (
                                    <motion.div
                                      initial={{ opacity: 0, y: 6 }}
                                      animate={{ opacity: 1, y: 0 }}
                                      style={{
                                        padding: 12,
                                        borderRadius: 12,
                                        background:
                                          CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].options.find(
                                            (o) => o.key === cbtAnswersAttestation[cbtIndexAttestation]
                                          )?.correct
                                            ? 'rgba(16, 185, 129, 0.1)'
                                            : 'rgba(239, 68, 68, 0.1)',
                                        border:
                                          CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].options.find(
                                            (o) => o.key === cbtAnswersAttestation[cbtIndexAttestation]
                                          )?.correct
                                            ? '1px solid rgba(16, 185, 129, 0.3)'
                                            : '1px solid rgba(239, 68, 68, 0.3)',
                                        fontSize: 12,
                                        color:
                                          CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].options.find(
                                            (o) => o.key === cbtAnswersAttestation[cbtIndexAttestation]
                                          )?.correct
                                            ? '#34D399'
                                            : '#F87171',
                                        marginTop: 12,
                                      }}
                                    >
                                      <div style={{ marginBottom: 10 }}>
                                        {CBT_QUESTIONS_ATTESTATION[cbtIndexAttestation].explanation}
                                      </div>
                                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                                        {cbtIndexAttestation < 2 ? (
                                          <button
                                            type="button"
                                            onClick={() => setCbtIndexAttestation((i) => i + 1)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: '#F59E0B',
                                              color: '#090d16',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Keyingi savol ({cbtIndexAttestation + 2}/3) →
                                          </button>
                                        ) : (
                                          <button
                                            type="button"
                                            onClick={() => setCbtFinishedAttestation(true)}
                                            style={{
                                              padding: '6px 14px',
                                              borderRadius: 8,
                                              background: 'linear-gradient(135deg, #10B981, #059669)',
                                              color: '#FFFFFF',
                                              fontSize: 11,
                                              fontWeight: 800,
                                              border: 'none',
                                              cursor: 'pointer',
                                            }}
                                          >
                                            Natijani ko&apos;rish 🏁
                                          </button>
                                        )}
                                      </div>
                                    </motion.div>
                                  )}
                                </motion.div>
                              </AnimatePresence>
                            ) : (
                              <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.22 }}
                                style={{
                                  padding: '20px 16px',
                                  borderRadius: 16,
                                  background: 'var(--card-2)',
                                  border: '1px solid var(--border)',
                                  textAlign: 'center',
                                }}
                              >
                                {(() => {
                                  const correctCount = [0, 1, 2].filter((i) => {
                                    const a = cbtAnswersAttestation[i];
                                    return a && CBT_QUESTIONS_ATTESTATION[i].options.find((o) => o.correct)?.key === a;
                                  }).length;
                                  return (
                                    <>
                                      <div style={{ fontSize: 32, marginBottom: 8 }}>
                                        {correctCount === 3 ? '🏆' : correctCount >= 2 ? '🎉' : '📚'}
                                      </div>
                                      <div
                                        style={{
                                          fontSize: 16,
                                          fontWeight: 800,
                                          color: 'var(--ink)',
                                          marginBottom: 4,
                                        }}
                                      >
                                        Mini CBT Sinovi Yakunlandi!
                                      </div>
                                      <div
                                        style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: 6,
                                          padding: '4px 14px',
                                          borderRadius: 999,
                                          background:
                                            correctCount === 3
                                              ? 'rgba(16, 185, 129, 0.2)'
                                              : 'rgba(245, 158, 11, 0.2)',
                                          color: correctCount === 3 ? '#10B981' : '#F59E0B',
                                          fontSize: 13,
                                          fontWeight: 800,
                                          marginBottom: 12,
                                        }}
                                      >
                                        Natija: {correctCount} / 3 To&apos;g&apos;ri ({Math.round((correctCount / 3) * 100)}%)
                                      </div>
                                      <p
                                        style={{
                                          fontSize: 12,
                                          color: 'var(--ink-soft)',
                                          lineHeight: 1.5,
                                          margin: '0 auto 16px',
                                          maxWidth: 320,
                                        }}
                                      >
                                        {correctCount >= 2
                                          ? "Muvaffaqiyatli sinov! Davlat attestatsiyasida Oliy toifa va 70% oylik ustama olish ehtimolingiz yuqori."
                                          : "Yaxshi boshlanish! Mavzular bo'yicha mustahkamlash mashqlarini bajarish tavsiya etiladi."}
                                      </p>
                                    </>
                                  );
                                })()}

                                <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
                                  <button
                                    type="button"
                                    onClick={() => handleAction('/tests')}
                                    className="btn-glow"
                                    style={{
                                      padding: '10px 18px',
                                      borderRadius: 12,
                                      background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                                      color: '#090d16',
                                      fontSize: 12,
                                      fontWeight: 800,
                                      border: 'none',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    To&apos;liq testni boshlash (50 ta savol) →
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setCbtIndexAttestation(0);
                                      setCbtAnswersAttestation({});
                                      setCbtFinishedAttestation(false);
                                    }}
                                    style={{
                                      padding: '10px 16px',
                                      borderRadius: 12,
                                      background: 'var(--card-2)',
                                      border: '1px solid var(--border)',
                                      color: 'var(--ink)',
                                      fontSize: 12,
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                    }}
                                  >
                                    Qayta ishlash ↺
                                  </button>
                                </div>
                              </motion.div>
                            )}
                          </div>
                        )}

                        {/* Attestation Tab 2: Toifa Diagnostikasi */}
                        {demoTabAttestation === 'diagnostic' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 14,
                              }}
                            >
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--muted)' }}>
                                50 talik Rasmiy Diagnostika
                              </span>
                              <div
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  padding: '4px 12px',
                                  borderRadius: 999,
                                  background: 'rgba(16, 185, 129, 0.15)',
                                  border: '1px solid rgba(16, 185, 129, 0.35)',
                                  color: '#34D399',
                                  fontWeight: 800,
                                  fontSize: 13,
                                }}
                              >
                                <span>46 / 50 ball (92%)</span>
                                <span style={{ fontSize: 11, opacity: 0.8 }}>(Oliy Toifa)</span>
                              </div>
                            </div>

                            {/* 3 Categories Breakdown */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                              {ATTESTATION_CATEGORIES.map((cat) => (
                                <div
                                  key={cat.id}
                                  style={{
                                    padding: '10px 14px',
                                    borderRadius: 12,
                                    background: 'var(--card-2)',
                                    border: '1px solid var(--border)',
                                  }}
                                >
                                  <div
                                    style={{
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      marginBottom: 6,
                                    }}
                                  >
                                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>
                                      {cat.name}
                                    </span>
                                    <span style={{ fontSize: 12, fontWeight: 800, color: '#F59E0B' }}>
                                      {cat.correct} / {cat.total} ({cat.percent}%)
                                    </span>
                                  </div>
                                  <div
                                    style={{
                                      width: '100%',
                                      height: 6,
                                      borderRadius: 999,
                                      background: 'rgba(255, 255, 255, 0.08)',
                                      overflow: 'hidden',
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: `${cat.percent}%`,
                                        height: '100%',
                                        borderRadius: 999,
                                        background: cat.percent >= 90 ? '#10B981' : '#F59E0B',
                                      }}
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>

                            {/* Attestation summary badge */}
                            <div
                              style={{
                                padding: 14,
                                borderRadius: 14,
                                background: 'rgba(245, 158, 11, 0.1)',
                                border: '1px solid rgba(245, 158, 11, 0.3)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 12,
                              }}
                            >
                              <div
                                style={{
                                  width: 40,
                                  height: 40,
                                  borderRadius: 10,
                                  background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                                  color: '#090d16',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontWeight: 900,
                                  fontSize: 20,
                                  flexShrink: 0,
                                }}
                              >
                                🏆
                              </div>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, fontWeight: 800, color: '#F59E0B' }}>
                                  Oliy toifa va 70% oylik ustama kafolatlandi!
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                                  Sinov natijangiz Davlat attestatsiya komissiyasi mezonlariga toʻliq javob beradi.
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </div>
        </section>

        {/* 3 CORE DIRECTIONS SECTION ("IMKONIYATLAR") */}
        <section
          id="features"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 1200 }}>
            <div style={{ textAlign: 'center', maxWidth: 680, margin: '0 auto 48px' }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {selectedTrack === 'ielts'
                  ? 'CAMBRIDGE & IDP IELTS ECOSYSTEM'
                  : selectedTrack === 'multilevel'
                  ? 'BMB / CEFR RASMIY STANDARTI'
                  : selectedTrack === 'attestation'
                  ? 'PEDAGOGLAR ATTESTATSIYASI 2026'
                  : t('features_main_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)',
                  fontWeight: 900,
                  color: 'var(--ink)',
                  margin: '12px 0',
                }}
              >
                {selectedTrack === 'ielts' ? (
                  <>
                    IELTS Band 7.5+ ga erishish imkoniyatlari{' '}
                    <span className="hero-title-gradient">bitta platformada</span>
                  </>
                ) : selectedTrack === 'multilevel' ? (
                  <>
                    Davlat Multi-level (B2/C1) imkoniyatlari{' '}
                    <span className="hero-title-gradient">bitta platformada</span>
                  </>
                ) : selectedTrack === 'attestation' ? (
                  <>
                    Toifa oshirish va 70% ustama olish uchun{' '}
                    <span className="hero-title-gradient">maxsus tizim</span>
                  </>
                ) : (
                  <>
                    {t('features_main_title_1')}{' '}
                    <span className="hero-title-gradient">{t('features_main_title_2')}</span>
                  </>
                )}
              </h2>
              <p style={{ fontSize: 15, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
                {selectedTrack === 'ielts'
                  ? 'Writing Task 1 & 2, real-vaqt Speaking simulyatori va Cambridge CBT testlari.'
                  : selectedTrack === 'multilevel'
                  ? 'DTM/BMB formati boʻyicha yozma insho, 35 talik CBT testlar va leksik trenajyorlar.'
                  : selectedTrack === 'attestation'
                  ? '50 talik rasmiy sinov formati, pedagogik mahorat va toifa ehtimolligi kalkulyatori.'
                  : t('features_main_subtitle')}
              </p>
            </div>

            {/* 3 Core Direction Cards Grid */}
            <AnimatePresence mode="wait">
              <motion.div
                key={selectedTrack}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.22 }}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                  gap: 24,
                }}
              >
                {/* IELTS 3 Cards */}
                {selectedTrack === 'ielts' && (
                  <>
                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38BDF8' }}>
                          <PenLineIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                          Task 1 & 2
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        IELTS Writing AI Grader
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Cambridge 4 ta mezoni (TR, CC, LR, GRA) boʻyicha 15 soniyada toʻliq baholash, xatolar tuzatmasi va Band prognozi.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Task 1 (Grafiklar) va Task 2 (Esse) toʻliq qoʻllab-quvvatlash</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Akademik lugʻat boyligi va sinonimlar tavsiyasi</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Band 7.5+ namunaviy insholar bilan solishtirish</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/speaking')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.35)', color: '#38BDF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_ielts_w_btn')}
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34D399' }}>
                          <Mic size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          Part 1, 2, 3
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feat_ielts_spk_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feat_ielts_spk_sub')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Part 2 Cue Card va 1 daqiqalik tayyorgarlik taymeri</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Grammatik va talaffuz xatolarini audio orqali koʻrsatish</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Jonli ELO reyting va boshqa oʻquvchilar bilan solishtirish</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/speaking')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_ielts_spk_btn')}
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818CF8' }}>
                          <Headphones size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(99, 102, 241, 0.15)', color: '#818CF8', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                          Reading & Listening
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feat_ielts_cbt_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feat_ielts_cbt_sub')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Cambridge 10–19 rasmiy test savollari</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Vaqt nazorati va avtomatik Band hisoblash</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Tezkor xatolar ustida ishlash rejimi</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.35)', color: '#818CF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_ielts_cbt_btn')}
                      </button>
                    </div>
                  </>
                )}

                {/* Multi-level 3 Cards */}
                {selectedTrack === 'multilevel' && (
                  <>
                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818CF8' }}>
                          <PenLineIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(99, 102, 241, 0.15)', color: '#818CF8', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                          B2 / C1 Insho
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        CEFR Writing AI Tahlili
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Davlat BMB standarti boʻyicha rasmiy insho va rasmiy xatlar tekshiruvi, leksik boylik va grammatik aniqlik.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Part 1 (Xat/Email) va Part 2 (Esse) 20 ballik tizimda</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>B2 va C1 darajasiga mos soʻz birikmalari tahlili</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Xatolar tuzatmasi bilan bir zumda hisobot</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/essays')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.35)', color: '#818CF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_multi_w_btn')}
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38BDF8' }}>
                          <FileTextIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                          35 talik Savollar
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feat_multi_cbt_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feat_multi_cbt_sub')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Haqiqiy imtihon interfeysi va taymer</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Savollar boʻyicha batafsil izoh va tushuntirish</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>B1, B2, C1 darajasi ehtimolligi kalkulyatori</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.35)', color: '#38BDF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_multi_cbt_btn')}
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34D399' }}>
                          <SwordsIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          B1 · B2 · C1
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Lugʻat va Grammatika Arenasi
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        CEFR darajalari uchun maxsus leksik mini-trenajyorlar va boshqa abituriyentlar bilan 1v1 viktorinalar.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Oxford 3000 & 5000 soʻzlar bazasi</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>1v1 intellektual bellashuv va ball toʻplash</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Kundalik soʻz yodlash maratoni (Streak)</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/arena')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        Arenaga kirish →
                      </button>
                    </div>
                  </>
                )}

                {/* National Certificate 3 Cards */}
                {selectedTrack === 'national_certificate' && (
                  <>
                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F59E0B' }}>
                          <PenLineIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                          {t('feature_card_essay_badge')}
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_essay_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_essay_desc')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>{t('feature_card_essay_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>{t('feature_card_essay_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>{t('feature_card_essay_bullet3')}</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/essays')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.35)', color: '#F59E0B', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feature_card_essay_action')}
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10B981' }}>
                          <FileTextIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          {t('feature_card_tests_badge')}
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_tests_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_tests_desc')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_tests_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_tests_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_tests_bullet3')}</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feature_card_tests_action')}
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(139, 92, 246, 0.12)', border: '1px solid rgba(139, 92, 246, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8B5CF6' }}>
                          <SwordsIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(139, 92, 246, 0.15)', color: '#8B5CF6', border: '1px solid rgba(139, 92, 246, 0.3)' }}>
                          {t('feature_card_arena_badge')}
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_arena_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_arena_desc')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#8B5CF6' }} />
                          <span>{t('feature_card_arena_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#8B5CF6' }} />
                          <span>{t('feature_card_arena_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#8B5CF6' }} />
                          <span>{t('feature_card_arena_bullet3')}</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/arena')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(139, 92, 246, 0.15)', border: '1px solid rgba(139, 92, 246, 0.35)', color: '#A78BFA', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feature_card_arena_action')}
                      </button>
                    </div>
                  </>
                )}

                {/* Attestation 3 Cards */}
                {selectedTrack === 'attestation' && (
                  <>
                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F59E0B' }}>
                          <FileTextIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                          50 talik Format
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Attestatsiya Simulyatori
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Mutaxassislik fani (35), Kasbiy standart (5) va Pedagogik mahorat (10) savollarini oʻz ichiga olgan rasmiy sinov formati.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Haqiqiy davlat test tizimiga 100% mos vaqt taymeri</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Grammatika va adabiyot boʻyicha chuqur tahlillar</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Barcha xatolarni boʻlimlar boʻyicha koʻrsatish</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.35)', color: '#F59E0B', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        50 talik testni boshlash →
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10B981' }}>
                          <LightbulbIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          Metodika & Keyslar
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Pedagogik Mahorat Trenajyori
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Yangi milliy oʻquv dasturi, 4K koʻnikmalari va formativ baholash metodikasi boʻyicha amaliy keys savollari.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Dars tahlili va interaktiv metodlar boʻyicha amaliyot</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Inklyuziv taʻlim va oʻquvchi psixologiyasi savollari</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Davlat taʻlim standarti qonunchiligi asosidagi keyslar</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        Metodik keyslarni yechish →
                      </button>
                    </div>

                    <div className="glass-card lcard-hover" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(59, 130, 246, 0.12)', border: '1px solid rgba(59, 130, 246, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3B82F6' }}>
                          <TrophyIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(59, 130, 246, 0.15)', color: '#3B82F6', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
                          70% Ustama
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Toifa va Ustama Prognozi
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        1-toifa va Oliy toifaga erishish ehtimolligi hamda oylik maoshga qoʻshiladigan 70% ustama kalkulyatori.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#3B82F6' }} />
                          <span>86+ ball bilan Oliy toifa uchun individual reja</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#3B82F6' }} />
                          <span>Kuchsiz boʻlimlarni avtomatik aniqlash va kuchaytirish</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#3B82F6' }} />
                          <span>Attestatsiyagacha qolgan vaqt boʻyicha tayyorgarlik</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/profile')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.35)', color: '#60A5FA', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        Toifa rejasini tuzish →
                      </button>
                    </div>
                  </>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </section>

        {/* STATS SECTION */}
        <section id="stats" style={{ padding: '40px 20px 60px' }}>
          <div style={{ margin: '0 auto', maxWidth: 1200 }}>
            {stats && (
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 16,
                  justifyContent: 'center',
                  marginBottom: 32,
                }}
              >
                {[
                  { label: t('stats_students'), val: stats.totals.students.toLocaleString('uz-UZ'), Icon: BotIcon, col: '#10B981' },
                  { label: t('stats_tests'), val: stats.totals.tests.toLocaleString('uz-UZ'), Icon: FileTextIcon, col: '#F59E0B' },
                  { label: t('stats_essays'), val: stats.totals.essays_graded.toLocaleString('uz-UZ'), Icon: PenLineIcon, col: '#8B5CF6' },
                ].map((item, i) => (
                  <div
                    key={i}
                    className="glass-card"
                    style={{
                      flex: '1 1 240px',
                      maxWidth: 360,
                      borderRadius: 18,
                      padding: '20px 24px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 16,
                    }}
                  >
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: 14,
                        background: `${item.col}1A`,
                        border: `1px solid ${item.col}33`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: item.col,
                      }}
                    >
                      <item.Icon size={22} />
                    </div>
                    <div>
                      <div style={{ fontSize: 24, fontWeight: 900, color: 'var(--ink)', lineHeight: 1.1 }}>
                        {item.val}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4, fontWeight: 600 }}>
                        {item.label}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {trendData.length > 0 && <TrendChart data={trendData} />}
          </div>
        </section>

        {/* HOW IT WORKS SECTION */}
        <HowItWorks />

        {/* COMPARISON TABLE */}
        <section
          id="comparison"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 960 }}>
            <div style={{ textAlign: 'center', maxWidth: 640, margin: '0 auto 40px' }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {t('cmp_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.4rem)',
                  fontWeight: 900,
                  color: 'var(--ink)',
                  margin: '12px 0',
                }}
              >
                {t('cmp_title_1')}{' '}
                <span className="hero-title-gradient">{t('cmp_title_2')}</span>
              </h2>
              <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
                {t('cmp_subtitle')}
              </p>
            </div>

            <div
              className="glass-card"
              style={{
                borderRadius: 20,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.4fr 1fr 1fr',
                  padding: '16px 20px',
                  background: 'var(--card-2)',
                  borderBottom: '1px solid var(--border)',
                  fontSize: 12,
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--muted)',
                }}
              >
                <div>{t('cmp_col_param')}</div>
                <div style={{ textAlign: 'center' }}>{t('cmp_col_traditional')}</div>
                <div style={{ textAlign: 'center', color: '#F59E0B' }}>GRAND EDUCATION AI</div>
              </div>

              {[
                [t('cmp_row_speed'), t('cmp_row_speed_trad'), t('cmp_row_speed_grand'), true],
                [t('cmp_row_criteria'), t('cmp_row_criteria_trad'), t('cmp_row_criteria_grand'), true],
                [t('cmp_row_practice'), t('cmp_row_practice_trad'), t('cmp_row_practice_grand'), true],
                [t('cmp_row_analytics'), t('cmp_row_analytics_trad'), t('cmp_row_analytics_grand'), true],
                [t('cmp_row_cost'), t('cmp_row_cost_trad'), t('cmp_row_cost_grand'), true],
              ].map(([param, trad, grand, isGood], i) => (
                <div
                  key={i}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1.4fr 1fr 1fr',
                    padding: '16px 20px',
                    borderBottom: i < 4 ? '1px solid var(--border)' : 'none',
                    fontSize: 13,
                    alignItems: 'center',
                  }}
                >
                  <div style={{ fontWeight: 700, color: 'var(--ink)' }}>{param}</div>
                  <div style={{ textAlign: 'center', color: 'var(--muted)' }}>{trad}</div>
                  <div
                    style={{
                      textAlign: 'center',
                      fontWeight: 800,
                      color: isGood ? '#10B981' : '#F59E0B',
                    }}
                  >
                    {grand}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* PRICING SECTION */}
        <section
          id="pricing"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 1240 }}>
            <div style={{ textAlign: 'center', maxWidth: 640, margin: '0 auto 48px' }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {t('pricing_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)',
                  fontWeight: 900,
                  color: 'var(--ink)',
                  margin: '12px 0',
                }}
              >
                {t('pricing_title_1')}{' '}
                <span className="hero-title-gradient">{t('pricing_title_2')}</span>
              </h2>
              <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
                {t('pricing_subtitle')}
              </p>
            </div>

            <div
              className="pricing-4col-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
              style={{
                display: 'grid',
                alignItems: 'stretch',
              }}
            >
              {/* 1. Free Plan */}
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'var(--card)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ fontSize: 17, fontWeight: 900, color: 'var(--ink)', marginBottom: 6 }}>
                  {t('plan_free_name')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_free_desc')}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: 'var(--ink)' }}>0</span>
                  <span style={{ fontSize: 13, color: 'var(--muted)' }}>{t('plan_free_period', "so'm / umrbod")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    t('plan_free_f1'),
                    t('plan_free_f2'),
                    t('plan_free_f3'),
                    t('plan_free_f4'),
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#10B981', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink-soft)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/register')}
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                    color: 'var(--ink)',
                    fontWeight: 700,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_free_cta')}
                </button>
              </div>

              {/* 2. Starter Plan (New) */}
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  border: '1px solid rgba(16, 185, 129, 0.45)',
                  boxShadow: '0 8px 30px rgba(16, 185, 129, 0.12)',
                  background: 'var(--card)',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: -11,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    padding: '3px 12px',
                    borderRadius: 999,
                    background: 'rgba(16, 185, 129, 0.2)',
                    border: '1px solid rgba(16, 185, 129, 0.4)',
                    color: '#10B981',
                    fontSize: 10.5,
                    fontWeight: 900,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                  }}
                >
                  ⚡ {t('plan_starter_badge', 'Yangi')}
                </div>
                <div style={{ fontSize: 17, fontWeight: 900, color: 'var(--ink)', marginBottom: 6 }}>
                  ⚡ {t('plan_starter_name', 'Starter')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_starter_desc', "Tezkor sinov va 5 ta to'liq test yechish imkoniyati")}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: '#10B981' }}>5 000</span>
                  <span style={{ fontSize: 13, color: 'var(--muted)' }}>{t('plan_starter_period', "so'm / to'plam")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    t('plan_starter_f1', "5 ta to'liq rasmiy Mock test"),
                    t('plan_starter_f2', '3 ta rasmiy mezonli esse tahlili'),
                    t('plan_starter_f3', 'Kuniga 10 ta AI repetitor izohi'),
                    t('plan_starter_f4', 'Xatolar va zaif mavzular tahlili'),
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#10B981', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink-soft)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/subscribe?plan=starter')}
                  className="btn-glow"
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #10B981, #059669)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: 800,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_starter_cta', 'Starter paketini olish')}
                </button>
              </div>

              {/* 3. Pro Plan (Popular) */}
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  border: '2px solid rgba(245, 158, 11, 0.6)',
                  boxShadow: '0 12px 36px rgba(245, 158, 11, 0.22)',
                  background: 'var(--card)',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: -12,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    padding: '4px 14px',
                    borderRadius: 999,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    color: '#090d16',
                    fontSize: 11,
                    fontWeight: 900,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                  }}
                >
                  🔥 {t('plan_pro_badge', 'Eng Ommabop')}
                </div>
                <div style={{ fontSize: 17, fontWeight: 900, color: 'var(--ink)', marginBottom: 6 }}>
                  🔥 {t('plan_pro_name')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_pro_desc')}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: '#F59E0B' }}>49 000</span>
                  <span style={{ fontSize: 13, color: 'var(--muted)' }}>{t('plan_pro_period', "so'm / oy")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    t('plan_pro_f1'),
                    t('plan_pro_f2'),
                    t('plan_pro_f3'),
                    t('plan_pro_f4'),
                    t('plan_pro_f5'),
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#F59E0B', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink-soft)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/subscribe?plan=pro')}
                  className="btn-glow"
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    border: 'none',
                    color: '#090d16',
                    fontWeight: 900,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_pro_cta')}
                </button>
              </div>

              {/* 4. Premium Plan (VIP) */}
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  border: '1px solid rgba(139, 92, 246, 0.5)',
                  boxShadow: '0 8px 32px rgba(139, 92, 246, 0.16)',
                  background: 'var(--card)',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: -11,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    padding: '3px 12px',
                    borderRadius: 999,
                    background: 'rgba(139, 92, 246, 0.2)',
                    border: '1px solid rgba(139, 92, 246, 0.4)',
                    color: '#A78BFA',
                    fontSize: 10.5,
                    fontWeight: 900,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                  }}
                >
                  👑 {t('plan_premium_badge', 'VIP / Cheksiz')}
                </div>
                <div style={{ fontSize: 17, fontWeight: 900, color: 'var(--ink)', marginBottom: 6 }}>
                  👑 {t('plan_master_name')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_master_desc')}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: '#A78BFA' }}>89 000</span>
                  <span style={{ fontSize: 13, color: 'var(--muted)' }}>{t('plan_master_period', "so'm / oy")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    t('plan_master_f1'),
                    t('plan_master_f2'),
                    t('plan_master_f3'),
                    t('plan_master_f4'),
                    t('plan_master_f5'),
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#8B5CF6', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink-soft)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/subscribe?plan=premium')}
                  className="btn-glow"
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #8B5CF6, #6366F1)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: 800,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_master_cta')}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section
          id="faq"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 840 }}>
            <div style={{ textAlign: 'center', marginBottom: 44 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {t('faq_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.4rem)',
                  fontWeight: 900,
                  color: 'var(--ink)',
                  margin: '12px 0',
                }}
              >
                {t('faq_title_1')}{' '}
                <span className="hero-title-gradient">{t('faq_title_2')}</span>
              </h2>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                [t('faq_q1'), t('faq_a1')],
                [t('faq_q2'), t('faq_a2')],
                [t('faq_q3'), t('faq_a3')],
                [t('faq_q4'), t('faq_a4')],
                [t('faq_q5'), t('faq_a5')],
              ].map(([q, a], i) => (
                <details
                  key={i}
                  className="glass-card"
                  style={{
                    borderRadius: 16,
                    padding: '16px 20px',
                    cursor: 'pointer',
                  }}
                >
                  <summary
                    style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: 'var(--ink)',
                      listStyle: 'none',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>{q}</span>
                    <span style={{ fontSize: 18, color: '#F59E0B' }}>+</span>
                  </summary>
                  <p
                    style={{
                      margin: '12px 0 0',
                      fontSize: 13,
                      color: 'var(--muted)',
                      lineHeight: 1.65,
                    }}
                  >
                    {a}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* BOTTOM CTA BANNER */}
        <section style={{ padding: '40px 20px 80px' }}>
          <div
            style={{
              margin: '0 auto',
              maxWidth: 1040,
              borderRadius: 28,
              padding: '48px 32px',
              textAlign: 'center',
              position: 'relative',
              overflow: 'hidden',
              background:
                landingSubject === 'english'
                  ? 'linear-gradient(135deg, rgba(56, 189, 248, 0.14), rgba(99, 102, 241, 0.12))'
                  : 'linear-gradient(135deg, rgba(245, 158, 11, 0.14), rgba(139, 92, 246, 0.12))',
              border:
                landingSubject === 'english'
                  ? '1px solid rgba(56, 189, 248, 0.3)'
                  : '1px solid rgba(245, 158, 11, 0.3)',
            }}
          >
            <h2
              style={{
                fontSize: 'clamp(2rem, 3.8vw, 2.8rem)',
                fontWeight: 900,
                color: 'var(--ink)',
                margin: '0 0 16px',
              }}
            >
              {selectedTrack === 'ielts'
                ? 'IELTS Band 7.5+ ga erishishga tayyormisiz?'
                : selectedTrack === 'multilevel'
                ? 'Multi-level C1 sertifikatini olishga tayyormisiz?'
                : selectedTrack === 'attestation'
                ? 'Oliy toifa va 70% ustama sinoviga tayyormisiz?'
                : t('cta_banner_title')}
            </h2>
            <p
              style={{
                fontSize: 15,
                color: 'var(--muted)',
                maxWidth: 580,
                margin: '0 auto 32px',
                lineHeight: 1.65,
              }}
            >
              {selectedTrack === 'ielts'
                ? 'Hozir roʻyxatdan oʻting va birinchi Writing hamda Speaking sinovini mutlaqo bepul topshiring!'
                : selectedTrack === 'multilevel'
                ? '35 talik namunaviy test va yozma insho tahlilidan bepul foydalaning.'
                : selectedTrack === 'attestation'
                ? '50 talik sinov diagnostikasini ishlab, toifa ehtimolligingizni aniqlang.'
                : t('cta_banner_subtitle')}
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => handleAction('/register')}
                className="btn-glow"
                style={{
                  padding: '14px 32px',
                  borderRadius: 14,
                  fontSize: 15,
                  fontWeight: 800,
                  color: '#090d16',
                  background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 4px 20px rgba(245, 158, 11, 0.4)',
                }}
              >
                {t('cta_banner_btn')} →
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--header-bg)',
          padding: '48px 20px 32px',
        }}
      >
        <div style={{ margin: '0 auto', maxWidth: 1200 }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 36,
              marginBottom: 40,
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <img src="/grandec.png" alt="GRANDEC" style={{ width: 32, height: 32, borderRadius: 8 }} />
                <span style={{ fontWeight: 900, fontSize: 16, color: 'var(--ink)' }}>GRAND EDUCATION</span>
              </div>
              <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
                {t('foot_desc')}
              </p>
            </div>

            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
                {t('foot_col_platform')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <Link to="/essays" style={{ color: 'var(--muted)', textDecoration: 'none' }}>AI Esse Grader</Link>
                <Link to="/tests" style={{ color: 'var(--muted)', textDecoration: 'none' }}>CBT Testlar</Link>
                <Link to="/speaking" style={{ color: 'var(--muted)', textDecoration: 'none' }}>AI Speaking</Link>
                <Link to="/arena" style={{ color: 'var(--muted)', textDecoration: 'none' }}>1v1 Arena</Link>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
                {t('foot_col_legal')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <Link to="/terms" style={{ color: 'var(--muted)', textDecoration: 'none' }}>{t('foot_terms')}</Link>
                <Link to="/privacy" style={{ color: 'var(--muted)', textDecoration: 'none' }}>{t('foot_privacy')}</Link>
                <Link to="/public-offer" style={{ color: 'var(--muted)', textDecoration: 'none' }}>{t('foot_offer')}</Link>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
                {t('foot_col_contact')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: 'var(--muted)' }}>
                <a href="https://t.me/uz_essaygrader_bot" target="_blank" rel="noreferrer" style={{ color: '#F59E0B', textDecoration: 'none' }}>
                  @uz_essaygrader_bot
                </a>
                <span>Toshkent, Oʻzbekiston</span>
              </div>
            </div>
          </div>

          <div
            style={{
              borderTop: '1px solid var(--border)',
              paddingTop: 24,
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              gap: 12,
              fontSize: 12,
              color: 'var(--muted)',
            }}
          >
            <span>&copy; {new Date().getFullYear()} GRAND EDUCATION (grandec.uz). {t('foot_rights')}</span>
            <span>
              Website <a href="https://www.instagram.com/rozievkomiljon/" target="_blank" rel="noopener noreferrer" style={{ color: '#fbbf24', textDecoration: 'underline' }}>Komiljon Roziyev</a> tomonidan ishlab chiqilgan
            </span>
          </div>
        </div>
      </footer>

      {/* Style overrides for media queries */}
      <style>{`
        @keyframes wavePulse {
          0%, 100% { height: 6px; }
          50% { height: 26px; }
        }
        .waveform-bar {
          width: 4px;
          border-radius: 999px;
          background: #38BDF8;
          transition: height 0.2s ease;
        }
        .waveform-bar.playing {
          animation: wavePulse 0.9s ease-in-out infinite;
        }
        .hero-subject-switcher {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px;
          background: var(--card-2);
          border: 1px solid var(--border);
          border-radius: 999px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.18);
          max-width: 100%;
        }
        .hero-switcher-btn {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 18px;
          border-radius: 999px;
          font-size: 13px;
          font-weight: 700;
          color: var(--muted);
          background: transparent;
          border: none;
          cursor: pointer;
          transition: all 0.2s ease;
          white-space: nowrap;
        }
        .hero-switcher-btn:hover {
          color: var(--ink);
        }
        .hero-switcher-btn.active {
          background: linear-gradient(135deg, #F59E0B, #FBBF24);
          color: #090d16;
          box-shadow: 0 2px 12px rgba(245, 158, 11, 0.35);
        }
        .hero-exam-switcher {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        .hero-exam-btn {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          border-radius: 12px;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          min-height: 42px;
          background: var(--card-2);
          border: 1px solid var(--border);
          color: var(--muted);
          transition: all 0.2s ease;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }
        .hero-exam-btn:hover {
          border-color: rgba(245, 158, 11, 0.4);
          color: var(--ink);
        }
        .hero-exam-btn.active.active-eng {
          background: rgba(56, 189, 248, 0.16);
          border: 1px solid #38BDF8;
          color: #38BDF8;
          box-shadow: 0 4px 14px rgba(56, 189, 248, 0.25);
        }
        .hero-exam-btn.active.active-uz {
          background: rgba(245, 158, 11, 0.16);
          border: 1px solid #F59E0B;
          color: #F59E0B;
          box-shadow: 0 4px 14px rgba(245, 158, 11, 0.25);
        }
        .exam-btn-badge {
          font-size: 11px;
          font-weight: 800;
          padding: 2px 7px;
          border-radius: 6px;
          background: rgba(255, 255, 255, 0.08);
        }
        .switcher-subtag {
          font-size: 11px;
          font-weight: 800;
          padding: 2px 8px;
          border-radius: 6px;
          background: rgba(9, 13, 22, 0.22);
          color: inherit;
        }
        .hero-switcher-btn:not(.active) .switcher-subtag {
          background: var(--border);
          color: var(--muted);
        }
        @media (max-width: 640px) {
          .hero-subject-switcher {
            width: 100%;
            border-radius: 16px;
            flex-direction: column;
            gap: 4px;
            padding: 4px;
          }
          .hero-switcher-btn {
            width: 100%;
            border-radius: 12px;
            justify-content: center;
            padding: 10px 14px;
          }
          .hero-exam-switcher {
            width: 100%;
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
          }
          .hero-exam-btn {
            width: 100%;
            justify-content: center;
            min-height: 44px;
          }
        }
        @media (min-width: 900px) {
          .hero-grid {
            grid-template-columns: 1.05fr 0.95fr !important;
          }
          .landing-desktop-nav {
            display: flex !important;
          }
          .landing-burger-btn {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
