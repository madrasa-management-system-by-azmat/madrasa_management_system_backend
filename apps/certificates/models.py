import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class CertificateNumberSequence(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificate_number_sequences")
    year = models.PositiveSmallIntegerField()
    prefix = models.CharField(max_length=10)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "year", "prefix"], name="unique_certificate_sequence")]


class CertificateTemplate(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificate_templates")
    code = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=250)
    arabic_title = models.CharField(max_length=250, blank=True)
    subtitle = models.CharField(max_length=250, blank=True)
    body_text_male = models.TextField(help_text="Arabic/Urdu template for male students with placeholders")
    body_text_female = models.TextField(blank=True, help_text="Arabic/Urdu template for female students with placeholders")
    grade = models.CharField(max_length=100, default="ممتاز")
    dua = models.CharField(max_length=250, default="بارک اللّٰہ فی علمہٖ وعملہٖ فی الدارین")
    signatures = models.JSONField(default=list, blank=True)
    curriculum_books = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    @classmethod
    def ensure_defaults_for_madrasa(cls, madrasa):
        if cls.objects.filter(madrasa=madrasa).exists():
            return
        defaults = [
            {
                "code": "nazera",
                "title": "شَهَادَةُ خَتْمِ القُرْآنِ الكَرِيمِ (ناظرہ)",
                "arabic_title": "شَهَادَةُ خَتْمِ القُرْآنِ الكَرِيمِ",
                "subtitle": "شعبہ ناظرۂ قرآنِ کریم و ختمِ کلامِ پاک کی باقاعدہ تکمیل",
                "body_text_male": "الحمد لله رب العالمين والعاقبة للمتقين والصلوة والسلام على سيد المرسلين وخاتم النبيين وعلى اله واصحابه واتباعه اجمعين وبعد<br/>فيشهد مدير المدرسة <b>{principal_name}</b> بان الطالب <b>{student_name}</b> بن <b>{guardian_name}</b> من <b>{address}</b> قد اتم قراءة القرآن الحکیم کاملا ومکملا فی <b>{madrasa_name}</b> {location} عام {year} ء واراد المدير المدرسه شهادة القرآن الحکیم ويوصيه بتقوى الله عز وجل وان يتلو القرآن الحکیم آناء الليل وآناء النهار وان يعمل باحكامه وان يعلمه غیرهم والله الموفق والمعين -",
                "body_text_female": "الحمد لله رب العالمين والعاقبة للمتقين والصلوة والسلام على سيد المرسلين وخاتم النبيين وعلى اله واصحابه واتباعه اجمعين وبعد<br/>فيشهد مدير المدرسة <b>{principal_name}</b> بان الطالبة <b>{student_name}</b> بنت <b>{guardian_name}</b> من <b>{address}</b> قد اتمت قراءة القرآن الحکیم کاملا ومکملا فی <b>{madrasa_name}</b> {location} عام {year} ء واراد المدير المدرسه شهادة القرآن الحکیم ويوصيها بتقوى الله عز وجل وان تتلو القرآن الحکیم آناء الليل وآناء النهار وان تعمل باحكامه وان تعلمه غيرهن والله الموفق والمعين -",
                "grade": "۱۰۰ (ممتاز)",
                "dua": "بارک اللّٰہ فی علمہٖ وعملہٖ فی الدارین",
                "signatures": ["ختم المدرسة", "توقيع الاستاذ", "توقيع المدير"],
                "curriculum_books": [],
                "is_default": True,
            },
            {
                "code": "hifz",
                "title": "شَهَادَةُ حِفْظِ القُرْآنِ الكَرِيمِ (حفظ)",
                "arabic_title": "شَهَادَةُ حِفْظِ القُرْآنِ الكَرِيمِ",
                "subtitle": "شعبہ تحفیظِ قرآنِ کریم کی باوقار سند",
                "body_text_male": "الحمد لله رب العالمين والعاقبة للمتقين والصلوة والسلام على سيد المرسلين وخاتم النبيين وعلى اله واصحابه واتباعه اجمعين وبعد<br/>فيشهد مدير المدرسة <b>{principal_name}</b> بان الطالب <b>{student_name}</b> بن <b>{guardian_name}</b> من <b>{address}</b> قد اتم حفظ القرآن الحکیم کاملا ومکملا فی <b>{madrasa_name}</b> {location} عام {year} ء واراد المدير المدرسه شهادة القرآن الحکیم ويوصيه بتقوى الله عز وجل وان يتلو القرآن الحکیم آناء الليل وآناء النهار وان يعمل باحكامه وان يعلمه غيرهم والله الموفق والمعين -",
                "body_text_female": "الحمد لله رب العالمين والعاقبة للمتقين والصلوة والسلام على سيد المرسلين وخاتم النبيين وعلى اله واصحابه واتباعه اجمعين وبعد<br/>فيشهد مدير المدرسة <b>{principal_name}</b> بان الطالبة <b>{student_name}</b> بنت <b>{guardian_name}</b> من <b>{address}</b> قد اتمت حفظ القرآن الحکیم کاملا ومکملا فی <b>{madrasa_name}</b> {location} عام {year} ء واراد المدير المدرسه شهادة القرآن الحکیم ويوصيها بتقوى الله عز وجل وان تتلو القرآن الحکیم آناء الليل وآناء النهار وان تعمل باحكامه وان تعلمه غيرهن والله الموفق والمعين -",
                "grade": "۱۰۰ (ممتاز)",
                "dua": "بارک اللّٰہ فی علمہٖ وعملہٖ فی الدارین",
                "signatures": ["ختم المدرسة", "توقيع الاستاذ", "توقيع المدير"],
                "curriculum_books": [],
                "is_default": True,
            },
            {
                "code": "tarjama",
                "title": "شَهَادَةُ تَرْجَمَةِ القُرْآنِ الكَرِيمِ (ترجمہ)",
                "arabic_title": "شَهَادَةُ تَرْجَمَةِ القُرْآنِ الكَرِيمِ",
                "subtitle": "شعبہ ترجمۂ قرآنِ کریم و فہمِ قرآن کا نصاب",
                "body_text_male": "الحمد لله رب العالمين والعاقبة للمتقين والصلوة والسلام على سيد المرسلين وخاتم النبيين وعلى اله واصحابه واتباعه اجمعين وبعد<br/>فيشهد مدير المدرسة <b>{principal_name}</b> بان الطالب <b>{student_name}</b> ولد <b>{guardian_name}</b> من <b>{address}</b> قد اتم قراءة القرآن الحکیم وترجمته کاملا ومکملا فی <b>{madrasa_name}</b> {location} عام {year} ء واراد المدير المدرسه شهادة القرآن الحکیم ويوصيه بتقوى الله عز وجل وان يتلو القرآن الحکیم آناء الليل وآناء النهار وان يعمل باحكامه وان يعلمه غيره والله الموفق والمعين -",
                "body_text_female": "الحمد لله رب العالمين والعاقبة للمتقين والصلوة والسلام على سيد المرسلين وخاتم النبيين وعلى اله واصحابه واتباعه اجمعين وبعد<br/>فيشهد مدير المدرسة <b>{principal_name}</b> بان الطالبة <b>{student_name}</b> بنت <b>{guardian_name}</b> من <b>{address}</b> قد اتمت قراءة القرآن الحکیم وترجمته کاملا ومکملا فی <b>{madrasa_name}</b> {location} عام {year} ء واراد المدير المدرسه شهادة القرآن الحکیم ويوصيها بتقوى الله عز وجل وان تتلو القرآن الحکیم آناء الليل وآناء النهار وان تعمل باحكامه وان تعلمه غيرهن والله الموفق والمعين -",
                "grade": "۱۰۰ (ممتاز)",
                "dua": "بارک اللّٰہ فی علمہٖ وعملہٖ فی الدارین",
                "signatures": ["ختم المدرسة", "توقيع الاستاذ", "توقيع المدير"],
                "curriculum_books": [],
                "is_default": True,
            },
            {
                "code": "alimiyyah_first",
                "title": "شَهَادَةُ العَالِمِيَّةِ الاولى (عالمیہ اول)",
                "arabic_title": "شَهَادَةُ العَالِمِيَّةِ الاولى",
                "subtitle": "فِي العُلُومِ الإِسْلَامِيَّةِ وَالعَرَبِيَّة",
                "body_text_male": "الحَمْدُ لِلهِ وَكَفَى وَسَلَامٌ عَلَى عِبَادِهِ الَّذِينَ اصْطَفَى اما بعد فَتَشْهَدُ رِئَاسَةُ المَدْرَسَة <b>{madrasa_name}</b> الواقعه ببلدة {location}<br/>بِأَنَّ الاخَ الصَّالِحَ <b>{student_name}</b> وَلَدَ <b>{guardian_name}</b> مِن <b>{address}</b> قَدْ اتَمَّ الدِّرَاسَةَ النِّهَائِيَّةَ وَنَجَحَ فِي اخْتِبَارِهِ النِّهَائِي عَام {hijri_year}ھ بِمَطَابِق {year}ء بِتَقْدِيرِ جَيِّدٍ جِدّاً<br/>وَبِطَلَبِهِ تَمْنَحُ الرِّئَاسَةُ هَذِهِ الشَّهَادَةَ وَتُوصِيهِ ان يَخْشَى اللهَ سِرّاً وَعَلَانِيَةً وَيَتَّبِعَ السُّنَّةَ مُشْتَغِلاً بِنَشْرِ القُرْآنِ وَالحَدِيثِ وَالعُلُومِ الدِّينِيَّةِ مُقْتَفِياً لِآثَارِ السَّلَفِ الصَّالِحِينَ مُجْتَنِباً عَمَّا احْدَثَهُ المُبْتَدِعُونَ مِنَ الاخْتِرَاعِ فِي الدِّينِ عَاضّاً بِنَوَاجِذِهِ عَلَى مَا مَضَى عَلَيْهِ القُرُونُ المَشْهُودُ لَهَا بِالخَيْرِ مِنَ الصَّحَابَةِ وَالتَّابِعِينَ وَالأَئِمَّةِ المُجْتَهِدِينَ وَتَتَضَرَّعُ إِلَى اللهِ تَعَالَى ان يُوَفِّقَهُ لِخَيْرِ مَا يُحِبُّهُ وَيَرْضَاهُ وَاللهُ المُوَفِّقُ وَالمُعِينُ -",
                "body_text_female": "الحَمْدُ لِلهِ وَكَفَى وَسَلَامٌ عَلَى عِبَادِهِ الَّذِينَ اصْطَفَى اما بعد فَتَشْهَدُ رِئَاسَةُ المَدْرَسَة <b>{madrasa_name}</b> الواقعه ببلدة {location}<br/>بِأَنَّ الاخت الصَّالِحَة <b>{student_name}</b> بنت <b>{guardian_name}</b> مِن <b>{address}</b> قَدْ اتَمَّت الدِّرَاسَةَ النِّهَائِيَّةَ وَنَجَحَت فِي اخْتِبَارِهَا النِّهَائِي عَام {hijri_year}ھ بِمَطَابِق {year}ء بِتَقْدِيرِ جَيِّدٍ جِدّاً<br/>وَبِطَلَبِهَا تَمْنَحُ الرِّئَاسَةُ هَذِهِ الشَّهَادَةَ وَتُوصِيهَا ان تَخْشَى اللهَ سِرّاً وَعَلَانِيَةً وَتَتَّبِعَ السُّنَّةَ مُشْتَغِلَةً بِنَشْرِ القُرْآنِ وَالحَدِيثِ وَالعُلُومِ الدِّينِيَّةِ مُقْتَفِيَةً لِآثَارِ السَّلَفِ الصَّالِحِينَ مُجْتَنِبَةً عَمَّا احْدَثَهُ المُبْتَدِعُونَ مِنَ الاخْتِرَاعِ فِي الدِّينِ عَاضَّةً بِنَوَاجِذِهَا عَلَى مَا مَضَى عَلَيْهِ القُرُونُ المَشْهُودُ لَهَا بِالخَيْرِ مِنَ الصَّحَابَةِ وَالتَّابِعِينَ وَالأَئِمَّةِ المُجْتَهِدِينَ وَتَتَضَرَّعُ إِلَى اللهِ تَعَالَى ان يُوَفِّقَهَا لِخَيْرِ مَا يُحِبُّهُ وَيَرْضَاهُ وَاللهُ المُوَفِّقُ وَالمُعِينُ -",
                "grade": "جيد جدا (العالمية الاولى)",
                "dua": "بارک اللّٰہ فی علمہٖ وعملہٖ فی الدارین",
                "signatures": ["توقيعات الاساتذة", "توقيع رئيس المدرسة وختمه"],
                "curriculum_books": [],
                "is_default": True,
            },
            {
                "code": "alimiyyah",
                "title": "شَهَادَةُ العَالِمِيَّة (عالمیہ)",
                "arabic_title": "شَهَادَةُ العَالِمِيَّة",
                "subtitle": "فِي العُلُومِ الإِسْلَامِيَّةِ وَالعَرَبِيَّة",
                "body_text_male": "الحَمْدُ لِلهِ وَكَفَى وَسَلَامٌ عَلَى عِبَادِهِ الَّذِينَ اصْطَفَى اما بعد فَتَشْهَدُ رِئَاسَةُ المَدْرَسَة <b>{madrasa_name}</b> الواقعه ببلدة {location}<br/>بِأَنَّ الاخَ الصَّالِحَ <b>{student_name}</b> وَلَدَ <b>{guardian_name}</b> مِن <b>{address}</b> قَدْ اتَمَّ الدِّرَاسَةَ النِّهَائِيَّةَ وَنَجَحَ فِي اخْتِبَارِهِ النِّهَائِي عَام {hijri_year}ھ بِمَطَابِق {year}ء بِتَقْدِيرِ مُمْتَاز<br/>وَبِطَلَبِهِ تَمْنَحُ الرِّئَاسَةُ هَذِهِ الشَّهَادَةَ وَتُوصِيهِ ان يَخْشَى اللهَ سِرّاً وَعَلَانِيَةً وَيَتَّبِعَ السُّنَّةَ مُشْتَغِلاً بِنَشْرِ القُرْآنِ وَالحَدِيثِ وَالعُلُومِ الدِّينِيَّةِ مُقْتَفِياً لِآثَارِ السَّلَفِ الصَّالِحِينَ مُجْتَنِباً عَمَّا احْدَثَهُ المُبْتَدِعُونَ مِنَ الاخْتِرَاعِ فِي الدِّينِ عَاضّاً بِنَوَاجِذِهِ عَلَى مَا مَضَى عَلَيْهِ القُرُونُ المَشْهُودُ لَهَا بِالخَيْرِ مِنَ الصَّحَابَةِ وَالتَّابِعِينَ وَالأَئِمَّةِ المُجْتَهِدِينَ وَتَتَضَرَّعُ إِلَى اللهِ تَعَالَى ان يُوَفِّقَهُ لِخَيْرِ مَا يُحِبُّهُ وَيَرْضَاهُ وَاللهُ المُوَفِّقُ وَالمُعِينُ -",
                "body_text_female": "الحَمْدُ لِلهِ وَكَفَى وَسَلَامٌ عَلَى عِبَادِهِ الَّذِينَ اصْطَفَى اما بعد فَتَشْهَدُ رِئَاسَةُ المَدْرَسَة <b>{madrasa_name}</b> الواقعه ببلدة {location}<br/>بِأَنَّ الاخت الصَّالِحَة <b>{student_name}</b> بنت <b>{guardian_name}</b> مِن <b>{address}</b> قَدْ اتَمَّت الدِّرَاسَةَ النِّهَائِيَّةَ وَنَجَحَت فِي اخْتِبَارِهَا النِّهَائِي عَام {hijri_year}ھ بِمَطَابِق {year}ء بِتَقْدِيرِ مُمْتَاز<br/>وَبِطَلَبِهَا تَمْنَحُ الرِّئَاسَةُ هَذِهِ الشَّهَادَةَ وَتُوصِيهَا ان تَخْشَى اللهَ سِرّاً وَعَلَانِيَةً وَتَتَّبِعَ السُّنَّةَ مُشْتَغِلَةً بِنَشْرِ القُرْآنِ وَالحَدِيثِ وَالعُلُومِ الدِّينِيَّةِ مُقْتَفِيَةً لِآثَارِ السَّلَفِ الصَّالِحِينَ مُجْتَنِبَةً عَمَّا احْدَثَهُ المُبْتَدِعُونَ مِنَ الاخْتِرَاعِ فِي الدِّينِ عَاضَّةً بِنَوَاجِذِهَا عَلَى مَا مَضَى عَلَيْهِ القُرُونُ المَشْهُودُ لَهَا بِالخَيْرِ مِنَ الصَّحَابَةِ وَالتَّابِعِينَ وَالأَئِمَّةِ المُجْتَهِدِينَ وَتَتَضَرَّعُ إِلَى اللهِ تَعَالَى ان يُوَفِّقَهَا لِخَيْرِ مَا يُحِبُّهُ وَيَرْضَاهُ وَاللهُ المُوَفِّقُ وَالمُعِينُ -",
                "grade": "ممتاز (العالمية)",
                "dua": "بارک اللّٰہ فی علمہٖ وعملہٖ فی الدارین",
                "signatures": ["توقيعات الاساتذة", "توقيع رئيس المدرسة وختمه"],
                "curriculum_books": [],
                "is_default": True,
            },
            {
                "code": "tajweed",
                "title": "شَهَادَةُ التجويد والقراءة (تجوید)",
                "arabic_title": "شَهَادَةُ التجويد والقراءة",
                "subtitle": "علم القراءۃ والتجوید و کتبِ درسیہ کی باضابطہ تکمیل",
                "body_text_male": "الحمد لله الذى نزل على عبده الكتاب تنزيلاً وامرنا بقراءة القرآن ترتيلاً والصلوة والسلام على من بلّغه وكمّله تكميلاً - وبعد<br/>فان جامعة {madrasa_name} من احدى للمدارس الاسلامیہ الکبریٰ فی باکستان، التى تخدم الاسلام و تقوم بهمةٍ تدریس العلوم الاسلامیہ و نشرها تحفيظ القرآن الكريم و تجويده و تربیہ جیل صالح من المتخرجين كل عام و قد التحق بها فى قسم التجويد اخونا <b>{student_name}</b> ولد <b>{guardian_name}</b> عام {year} و قد نجح فى اختبار شهادة التجويد النهائى عام {year} بتقدير ممتاز والجامعة اذ تمنحه هذه الشهادة توصيه بتقوى الله سبحانه و تعالىٰ و اتباع ما عليه اهل السنة والجماعة والقيام بواجبه الدينى من بث الدعوة الاسلاميه والدفاع عن محيا الاسلام الباسم والله تعالى يوفقه و ايانا جميعاً -",
                "body_text_female": "الحمد لله الذى نزل على عبده الكتاب تنزيلاً وامرنا بقراءة القرآن ترتيلاً والصلوة والسلام على من بلّغه وكمّله تكميلاً - وبعد<br/>فان جامعة {madrasa_name} من احدى للمدارس الاسلامیہ الکبریٰ فی باکستان، التى تخدم الاسلام و تقوم بهمةٍ تدریس العلوم الاسلامیہ و نشرها تحفيظ القرآن الكريم و تجويده و تربیہ جیل صالح من المتخرجين كل عام و قد التحقت بها فى قسم التجويد اختنا <b>{student_name}</b> بنت <b>{guardian_name}</b> عام {year} و قد نجحت فى اختبار شهادة التجويد النهائى عام {year} بتقدير ممتاز والجامعة اذ تمنحها هذه الشهادة توصيها بتقوى الله سبحانه و تعالىٰ و اتباع ما عليه اهل السنة والجماعة والقيام بواجبها الدينى من بث الدعوة الاسلاميه والدفاع عن محيا الاسلام الباسم والله تعالى يوفقها و ايانا جميعاً -",
                "grade": "۵۵۰ (ممتاز)",
                "dua": "بارک اللّٰہ فی علمہٖ وعملہٖ فی الدارین",
                "signatures": ["توقيع المدرس", "توقيع رئيس المدرسين", "توقيع المدير", "ختم الجامعة"],
                "curriculum_books": ["معلم التجويد", "المقدمة الجزرية", "تفهيم الوقوف", "علوم القراءات"],
                "is_default": True,
            },
        ]
        objs = [cls(madrasa=madrasa, **d) for d in defaults]
        cls.objects.bulk_create(objs)


class Certificate(models.Model):
    class CertificateType(models.TextChoices):
        GRADUATION = "graduation", "Graduation"
        LEAVING = "leaving", "Leaving"
        NAZERA = "nazera", "Nazera Quran"
        HIFZ = "hifz", "Hifz Quran"
        TARJAMA = "tarjama", "Translation Quran"
        TAJWEED = "tajweed", "Tajweed & Qiraat"
        ALIMIYYAH = "alimiyyah", "Alimiyyah"
        ALIMIYYAH_FIRST = "alimiyyah_first", "Alimiyyah First (عالمیہ اول)"
        TRAINING = "training", "Training"
        REWARD = "reward", "Reward"
        MARKSHEET = "marksheet", "Marksheet"
        MANUAL = "manual", "Manual"

    class RecipientKind(models.TextChoices):
        STUDENT = "student", "Student"
        STAFF = "staff", "Staff"
        ALUMNI = "alumni", "Alumni"
        EXTERNAL = "external", "External"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        ISSUED = "issued", "Issued"
        REVOKED = "revoked", "Revoked"
        SUPERSEDED = "superseded", "Superseded"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificates")
    serial_number = models.CharField(max_length=80, unique=True)
    template = models.ForeignKey(CertificateTemplate, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates")
    certificate_type = models.CharField(max_length=50)
    recipient_kind = models.CharField(max_length=20, choices=RecipientKind.choices)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="certificates")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="certificates")
    alumni = models.ForeignKey("students.AlumniProfile", on_delete=models.PROTECT, blank=True, null=True, related_name="certificates")
    recipient_name_snapshot = models.CharField(max_length=250)
    recipient_identifier_snapshot = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=250)
    body_snapshot = models.TextField()
    issuer_snapshot = models.JSONField(default=dict)
    credential_snapshot = models.JSONField(default=dict)
    source_type = models.CharField(max_length=50, blank=True)
    source_object_id = models.PositiveBigIntegerField(blank=True, null=True)
    source_fingerprint = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    issued_on = models.DateField(blank=True, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_issued")
    issued_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_revoked")
    revoked_at = models.DateTimeField(blank=True, null=True)
    revocation_reason = models.TextField(blank=True)
    supersedes = models.OneToOneField("self", on_delete=models.SET_NULL, blank=True, null=True, related_name="superseded_by")
    revision_number = models.PositiveSmallIntegerField(default=1)
    payload_hash = models.CharField(max_length=64, blank=True)
    signature = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "source_fingerprint"], condition=~models.Q(source_fingerprint="") & models.Q(status__in=["approved", "issued"]), name="unique_active_source_certificate")]

    @classmethod
    def issue_serial(cls, madrasa, certificate_type):
        prefix_map = {
            "graduation": "GRD",
            "leaving": "LEV",
            "nazera": "NAZ",
            "hifz": "HFZ",
            "tarjama": "TRJ",
            "tajweed": "TJW",
            "alimiyyah": "ALM",
            "alimiyyah_first": "ALM1",
            "training": "TRN",
            "reward": "RWD",
            "marksheet": "MRK",
            "manual": "MAN",
        }
        prefix = prefix_map.get(certificate_type, certificate_type[:4].upper() if certificate_type else "CRT")
        year = timezone.localdate().year
        with transaction.atomic():
            sequence, _ = CertificateNumberSequence.objects.select_for_update().get_or_create(madrasa=madrasa, year=year, prefix=prefix, defaults={"next_value": 1})
            value = sequence.next_value
            sequence.next_value += 1
            sequence.save(update_fields=["next_value"])
        return f"{madrasa.slug.upper()}-{prefix}-{year}-{value:06d}"


class CertificateEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificate_events")
    certificate = models.ForeignKey(Certificate, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificate_events")
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class CertificateVerificationLog(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="verification_logs")
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificate_verification_logs")
    verified_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=20, choices=[("valid", "Valid"), ("revoked", "Revoked"), ("invalid", "Invalid")])
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-verified_at"]
