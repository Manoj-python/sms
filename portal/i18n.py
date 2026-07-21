"""English / Telugu / Hindi / Kannada strings. Language chosen via
/lang/{code} (cookie)."""

LANGS = ("en", "te", "hi", "kn")

STRINGS: dict[str, dict[str, str]] = {
    "brand": {
        "en": "SMSquare Credit Services", "te": "SMSquare క్రెడిట్ సర్వీసెస్",
        "hi": "SMSquare क्रेडिट सर्विसेज़", "kn": "SMSquare ಕ್ರೆಡಿಟ್ ಸರ್ವಿಸಸ್",
    },
    "tagline": {
        "en": "Vehicle Finance Customer Portal", "te": "వాహన ఫైనాన్స్ కస్టమర్ పోర్టల్",
        "hi": "वाहन वित्त ग्राहक पोर्टल", "kn": "ವಾಹನ ಹಣಕಾಸು ಗ್ರಾಹಕ ಪೋರ್ಟಲ್",
    },
    "login_title": {
        "en": "Login to your account", "te": "మీ ఖాతాలోకి లాగిన్ అవ్వండి",
        "hi": "अपने खाते में लॉगिन करें", "kn": "ನಿಮ್ಮ ಖಾತೆಗೆ ಲಾಗಿನ್ ಆಗಿ",
    },
    "mobile_number": {
        "en": "Registered mobile number", "te": "నమోదిత మొబైల్ నంబర్",
        "hi": "पंजीकृत मोबाइल नंबर", "kn": "ನೋಂದಾಯಿತ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ",
    },
    "send_otp": {"en": "Send OTP", "te": "OTP పంపండి", "hi": "OTP भेजें", "kn": "OTP ಕಳುಹಿಸಿ"},
    "enter_otp": {
        "en": "Enter the 6-digit OTP sent to", "te": "ఈ నంబర్‌కు పంపిన 6 అంకెల OTP నమోదు చేయండి",
        "hi": "इस नंबर पर भेजा गया 6-अंकों का OTP दर्ज करें", "kn": "ಈ ಸಂಖ್ಯೆಗೆ ಕಳುಹಿಸಲಾದ 6-ಅಂಕಿಗಳ OTP ನಮೂದಿಸಿ",
    },
    "verify_login": {
        "en": "Verify & Login", "te": "ధృవీకరించి లాగిన్ అవ్వండి",
        "hi": "सत्यापित करें और लॉगिन करें", "kn": "ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಲಾಗಿನ್ ಆಗಿ",
    },
    "resend_otp": {"en": "Resend OTP", "te": "OTP మళ్లీ పంపండి", "hi": "OTP दोबारा भेजें", "kn": "OTP ಮತ್ತೆ ಕಳುಹಿಸಿ"},
    "resend_wait": {
        "en": "You can resend in", "te": "మళ్లీ పంపడానికి వేచి ఉండండి",
        "hi": "आप इतने समय बाद दोबारा भेज सकते हैं", "kn": "ನೀವು ಇಷ್ಟು ಸಮಯದ ನಂತರ ಮತ್ತೆ ಕಳುಹಿಸಬಹುದು",
    },
    "alt_login": {
        "en": "Login with Agreement No. + Mobile + Date of Birth",
        "te": "అగ్రిమెంట్ నంబర్ + మొబైల్ + పుట్టిన తేదీతో లాగిన్",
        "hi": "एग्रीमेंट नंबर + मोबाइल + जन्म तिथि से लॉगिन करें",
        "kn": "ಒಪ್ಪಂದ ಸಂಖ್ಯೆ + ಮೊಬೈಲ್ + ಹುಟ್ಟಿದ ದಿನಾಂಕದೊಂದಿಗೆ ಲಾಗಿನ್ ಆಗಿ",
    },
    "mobile_login": {
        "en": "Login with mobile number", "te": "మొబైల్ నంబర్‌తో లాగిన్",
        "hi": "मोबाइल नंबर से लॉगिन करें", "kn": "ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯೊಂದಿಗೆ ಲಾಗಿನ್ ಆಗಿ",
    },
    "agreement_no": {
        "en": "Agreement number (e.g. LNTSPAR-240300005)",
        "te": "అగ్రిమెంట్ నంబర్ (ఉదా: LNTSPAR-240300005)",
        "hi": "एग्रीमेंट नंबर (उदा: LNTSPAR-240300005)",
        "kn": "ಒಪ್ಪಂದ ಸಂಖ್ಯೆ (ಉದಾ: LNTSPAR-240300005)",
    },
    "dob": {"en": "Date of birth", "te": "పుట్టిన తేదీ", "hi": "जन्म तिथि", "kn": "ಹುಟ್ಟಿದ ದಿನಾಂಕ"},
    "continue": {"en": "Continue", "te": "కొనసాగించండి", "hi": "जारी रखें", "kn": "ಮುಂದುವರಿಸಿ"},
    "logout": {"en": "Logout", "te": "లాగ్ అవుట్", "hi": "लॉग आउट", "kn": "ಲಾಗ್ ಔಟ್"},
    "welcome": {"en": "Welcome", "te": "స్వాగతం", "hi": "स्वागत है", "kn": "ಸ್ವಾಗತ"},
    "loading": {"en": "Please wait…", "te": "దయచేసి వేచి ఉండండి…", "hi": "कृपया प्रतीक्षा करें…", "kn": "ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ…"},
    "your_loans": {"en": "Your Loans", "te": "మీ రుణాలు", "hi": "आपके ऋण", "kn": "ನಿಮ್ಮ ಸಾಲಗಳು"},
    "view_profile": {
        "en": "View profile", "te": "ప్రొఫైల్ చూడండి", "hi": "प्रोफ़ाइल देखें", "kn": "ಪ್ರೊಫೈಲ್ ನೋಡಿ",
    },
    "profile": {"en": "Profile", "te": "ప్రొఫైల్", "hi": "प्रोफ़ाइल", "kn": "ಪ್ರೊಫೈಲ್"},
    "father_name": {
        "en": "Father's name", "te": "తండ్రి పేరు", "hi": "पिता का नाम", "kn": "ತಂದೆಯ ಹೆಸರು",
    },
    "aadhaar": {"en": "Aadhaar", "te": "ఆధార్", "hi": "आधार", "kn": "ಆಧಾರ್"},
    "address": {"en": "Address", "te": "చిరునామా", "hi": "पता", "kn": "ವಿಳಾಸ"},
    "product": {"en": "Product", "te": "ప్రొడక్ట్", "hi": "प्रोडक्ट", "kn": "ಉತ್ಪನ್ನ"},
    "emi": {"en": "EMI", "te": "EMI", "hi": "EMI", "kn": "EMI"},
    "next_due": {
        "en": "Next due", "te": "తదుపరి గడువు", "hi": "अगली किस्त की तारीख", "kn": "ಮುಂದಿನ ಬಾಕಿ ದಿನಾಂಕ",
    },
    "expired": {"en": "Expired", "te": "గడువు ముగిసింది", "hi": "समाप्त", "kn": "ಅವಧಿ ಮುಗಿದಿದೆ"},
    "overdue": {"en": "Overdue", "te": "బకాయి", "hi": "बकाया", "kn": "ಬಾಕಿ"},
    "dpd": {
        "en": "Days past due", "te": "గడువు దాటిన రోజులు",
        "hi": "देय तिथि से बीते दिन", "kn": "ಬಾಕಿ ದಿನಾಂಕದಿಂದ ಕಳೆದ ದಿನಗಳು",
    },
    "status": {"en": "Status", "te": "స్థితి", "hi": "स्थिति", "kn": "ಸ್ಥಿತಿ"},
    "view_pay": {
        "en": "View dues & pay", "te": "బకాయిలు చూసి చెల్లించండి",
        "hi": "बकाया देखें और भुगतान करें", "kn": "ಬಾಕಿ ನೋಡಿ ಮತ್ತು ಪಾವತಿಸಿ",
    },
    "loan_details": {
        "en": "Loan Details", "te": "రుణ వివరాలు", "hi": "ऋण विवरण", "kn": "ಸಾಲದ ವಿವರಗಳು",
    },
    "download_statement": {
        "en": "Download statement (PDF)", "te": "స్టేట్‌మెంట్ డౌన్‌లోడ్ (PDF)",
        "hi": "स्टेटमेंट डाउनलोड करें (PDF)", "kn": "ಸ್ಟೇಟ್‌ಮೆಂಟ್ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ (PDF)",
    },
    "download_foreclosure_statement": {
        "en": "Download foreclosure statement (PDF)", "te": "ఫోర్‌క్లోజర్ స్టేట్‌మెంట్ డౌన్‌లోడ్ (PDF)",
        "hi": "फोरक्लोज़र स्टेटमेंट डाउनलोड करें (PDF)", "kn": "ಫೋರ್‌ಕ್ಲೋಶರ್ ಸ್ಟೇಟ್‌ಮೆಂಟ್ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ (PDF)",
    },
    "customer_name": {
        "en": "Customer name", "te": "కస్టమర్ పేరు", "hi": "ग्राहक का नाम", "kn": "ಗ್ರಾಹಕರ ಹೆಸರು",
    },
    "loan_type": {"en": "Loan type", "te": "రుణ రకం", "hi": "ऋण प्रकार", "kn": "ಸಾಲದ ಪ್ರಕಾರ"},
    "region": {"en": "Region", "te": "ప్రాంతం", "hi": "क्षेत्र", "kn": "ಪ್ರದೇಶ"},
    "branch": {"en": "Branch", "te": "బ్రాంచ్", "hi": "शाखा", "kn": "ಶಾಖೆ"},
    "vehicle_no": {"en": "Vehicle No.", "te": "వాహన నంబర్", "hi": "वाहन नंबर", "kn": "ವಾಹನ ಸಂಖ್ಯೆ"},
    "vehicle_class": {"en": "Vehicle Class", "te": "వాహన తరగతి", "hi": "वाहन श्रेणी", "kn": "ವಾಹನ ವರ್ಗ"},
    "loan_amount": {
        "en": "Loan amount", "te": "రుణ మొత్తం", "hi": "ऋण राशि", "kn": "ಸಾಲದ ಮೊತ್ತ",
    },
    "total_emi": {"en": "Total EMIs", "te": "మొత్తం EMIలు", "hi": "कुल EMI", "kn": "ಒಟ್ಟು EMIಗಳು"},
    "no_of_emi_received": {
        "en": "EMIs received", "te": "అందిన EMIలు", "hi": "प्राप्त EMI", "kn": "ಸ್ವೀಕರಿಸಿದ EMIಗಳು",
    },
    "emi_due_count": {
        "en": "EMIs due", "te": "బకాయి EMIలు", "hi": "बकाया EMI", "kn": "ಬಾಕಿ EMIಗಳು",
    },
    "emi_overdue": {"en": "EMI overdue", "te": "EMI బకాయి", "hi": "EMI बकाया", "kn": "EMI ಬಾಕಿ"},
    "late_charges": {
        "en": "Late charges", "te": "ఆలస్య ఛార్జీలు", "hi": "विलंब शुल्क", "kn": "ವಿಳಂಬ ಶುಲ್ಕ",
    },
    "vas_charges": {"en": "VAS charges", "te": "VAS ఛార్జీలు", "hi": "VAS शुल्क", "kn": "VAS ಶುಲ್ಕ"},
    "total_due": {"en": "Total due", "te": "మొత్తం బకాయి", "hi": "कुल बकाया", "kn": "ಒಟ್ಟು ಬಾಕಿ"},
    "dues_title": {
        "en": "Current Dues", "te": "ప్రస్తుత బకాయిలు", "hi": "वर्तमान बकाया", "kn": "ಪ್ರಸ್ತುತ ಬಾಕಿ",
    },
    "due_emi": {"en": "EMI due", "te": "EMI బకాయి", "hi": "EMI बकाया", "kn": "EMI ಬಾಕಿ"},
    "penal_charges": {
        "en": "Penal charges (LPI)", "te": "జరిమానా ఛార్జీలు (LPI)",
        "hi": "दंड शुल्क (LPI)", "kn": "ದಂಡ ಶುಲ್ಕ (LPI)",
    },
    "collection_charges": {
        "en": "Collection charges", "te": "వసూలు ఛార్జీలు",
        "hi": "वसूली शुल्क", "kn": "ಸಂಗ್ರಹಣಾ ಶುಲ್ಕ",
    },
    "total_payable": {
        "en": "Total payable", "te": "మొత్తం చెల్లించవలసినది",
        "hi": "कुल देय राशि", "kn": "ಒಟ್ಟು ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ",
    },
    "penal_disclosure": {
        "en": "Penal charges are levied as per your loan agreement and RBI guidelines. The break-up above is disclosed in full before you pay.",
        "te": "జరిమానా ఛార్జీలు మీ రుణ ఒప్పందం మరియు RBI మార్గదర్శకాల ప్రకారం విధించబడతాయి. చెల్లించే ముందు పూర్తి వివరాలు పైన చూపబడ్డాయి.",
        "hi": "दंड शुल्क आपके ऋण अनुबंध और RBI दिशानिर्देशों के अनुसार लगाया जाता है। भुगतान करने से पहले ऊपर पूरा विवरण दिखाया गया है।",
        "kn": "ದಂಡ ಶುಲ್ಕವನ್ನು ನಿಮ್ಮ ಸಾಲ ಒಪ್ಪಂದ ಮತ್ತು RBI ಮಾರ್ಗಸೂಚಿಗಳ ಪ್ರಕಾರ ವಿಧಿಸಲಾಗುತ್ತದೆ. ಪಾವತಿಸುವ ಮೊದಲು ಮೇಲಿನ ಸಂಪೂರ್ಣ ವಿವರಗಳನ್ನು ತಿಳಿಸಲಾಗಿದೆ.",
    },
    "pay_option": {
        "en": "How much would you like to pay?", "te": "మీరు ఎంత చెల్లించాలనుకుంటున్నారు?",
        "hi": "आप कितना भुगतान करना चाहेंगे?", "kn": "ನೀವು ಎಷ್ಟು ಪಾವತಿಸಲು ಬಯಸುತ್ತೀರಿ?",
    },
    "pay_total": {"en": "Total due", "te": "మొత్తం బకాయి", "hi": "कुल बकाया", "kn": "ಒಟ್ಟು ಬಾಕಿ"},
    "pay_emi": {
        "en": "Minimum EMI Amount", "te": "కనీస EMI మొత్తం",
        "hi": "न्यूनतम EMI राशि", "kn": "ಕನಿಷ್ಠ EMI ಮೊತ್ತ",
    },
    "minimum_emi_amount": {
        "en": "Minimum EMI Amount", "te": "కనీస EMI మొత్తం",
        "hi": "न्यूनतम EMI राशि", "kn": "ಕನಿಷ್ಠ EMI ಮೊತ್ತ",
    },
    "pay_part": {
        "en": "Any other payment", "te": "ఇతర చెల్లింపు", "hi": "कोई अन्य भुगतान", "kn": "ಬೇರೆ ಯಾವುದೇ ಪಾವತಿ",
    },
    "pay_part_zero_due": {
        "en": "Advance EMI or Foreclosure Amount", "te": "అడ్వాన్స్ EMI లేదా ఫోర్‌క్లోజర్ మొత్తం",
        "hi": "एडवांस EMI या फोरक्लोज़र राशि", "kn": "ಅಡ್ವಾನ್ಸ್ EMI ಅಥವಾ ಫೋರ್‌ಕ್ಲೋಶರ್ ಮೊತ್ತ",
    },
    "enter_payment_amount": {
        "en": "Please enter the amount you want to pay", "te": "మీరు చెల్లించాలనుకుంటున్న మొత్తాన్ని నమోదు చేయండి",
        "hi": "कृपया वह राशि दर्ज करें जो आप भुगतान करना चाहते हैं", "kn": "ದಯವಿಟ್ಟು ನೀವು ಪಾವತಿಸಲು ಬಯಸುವ ಮೊತ್ತವನ್ನು ನಮೂದಿಸಿ",
    },
    "show_qr": {
        "en": "Show UPI QR code", "te": "UPI QR కోడ్ చూపించండి",
        "hi": "UPI QR कोड दिखाएं", "kn": "UPI QR ಕೋಡ್ ತೋರಿಸಿ",
    },
    "pay_now": {
        "en": "Pay Now (UPI / Card / Netbanking)", "te": "ఇప్పుడే చెల్లించండి (UPI / కార్డ్ / నెట్‌బ్యాంకింగ్)",
        "hi": "अभी भुगतान करें (UPI / कार्ड / नेट बैंकिंग)", "kn": "ಈಗ ಪಾವತಿಸಿ (UPI / ಕಾರ್ಡ್ / ನೆಟ್ ಬ್ಯಾಂಕಿಂಗ್)",
    },
    "sms_link": {
        "en": "Or get payment link by SMS", "te": "లేదా SMS ద్వారా చెల్లింపు లింక్ పొందండి",
        "hi": "या SMS द्वारा भुगतान लिंक प्राप्त करें", "kn": "ಅಥವಾ SMS ಮೂಲಕ ಪಾವತಿ ಲಿಂಕ್ ಪಡೆಯಿರಿ",
    },
    "payment_success": {
        "en": "Payment received!", "te": "చెల్లింపు అందింది!",
        "hi": "भुगतान प्राप्त हुआ!", "kn": "ಪಾವತಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ!",
    },
    "account_updating": {
        "en": "Your payment will be processed once we get confirmation from the payment gateway.",
        "te": "పేమెంట్ గేట్‌వే నుండి నిర్ధారణ వచ్చిన తర్వాత మీ చెల్లింపు ప్రాసెస్ చేయబడుతుంది.",
        "hi": "पेमेंट गेटवे से पुष्टि मिलते ही आपका भुगतान प्रोसेस किया जाएगा।",
        "kn": "ಪಾವತಿ ಗೇಟ್‌ವೇಯಿಂದ ದೃಢೀಕರಣ ಬಂದ ನಂತರ ನಿಮ್ಮ ಪಾವತಿಯನ್ನು ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲಾಗುತ್ತದೆ.",
    },
    "download_receipt": {
        "en": "Download receipt (PDF)", "te": "రసీదు డౌన్‌లోడ్ (PDF)",
        "hi": "रसीद डाउनलोड करें (PDF)", "kn": "ರಸೀದಿ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ (PDF)",
    },
    "payment_history": {
        "en": "Payment History", "te": "చెల్లింపుల చరిత్ర", "hi": "भुगतान इतिहास", "kn": "ಪಾವತಿ ಇತಿಹಾಸ",
    },
    "downloads": {"en": "Downloads", "te": "డౌన్‌లోడ్‌లు", "hi": "डाउनलोड", "kn": "ಡೌನ್‌ಲೋಡ್‌ಗಳು"},
    "downloads_title": {
        "en": "Statement & Receipts", "te": "స్టేట్‌మెంట్ & రసీదులు",
        "hi": "स्टेटमेंट और रसीदें", "kn": "ಸ್ಟೇಟ್‌ಮೆಂಟ್ ಮತ್ತು ರಸೀದಿಗಳು",
    },
    "payment_date": {
        "en": "Payment Date", "te": "చెల్లింపు తేదీ", "hi": "भुगतान तिथि", "kn": "ಪಾವತಿ ದಿನಾಂಕ",
    },
    "amount": {"en": "Amount", "te": "మొత్తం", "hi": "राशि", "kn": "ಮೊತ್ತ"},
    "no_receipts_yet": {
        "en": "No payments recorded yet.", "te": "ఇంకా చెల్లింపులు నమోదు కాలేదు.",
        "hi": "अभी तक कोई भुगतान दर्ज नहीं हुआ है।", "kn": "ಇನ್ನೂ ಯಾವುದೇ ಪಾವತಿ ದಾಖಲಾಗಿಲ್ಲ.",
    },
    "contact_required_title": {
        "en": "Please Contact Us", "te": "దయచేసి మమ్మల్ని సంప్రదించండి",
        "hi": "कृपया हमसे संपर्क करें", "kn": "ದಯವಿಟ್ಟು ನಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸಿ",
    },
    "contact_required_message": {
        "en": "You currently have {count} EMI(s) due. To download your statement or payment history, please clear your dues first, or contact us for assistance.",
        "te": "మీకు ప్రస్తుతం {count} EMI(లు) బకాయి ఉన్నాయి. మీ స్టేట్‌మెంట్ లేదా చెల్లింపుల చరిత్రను డౌన్‌లోడ్ చేయడానికి, దయచేసి ముందుగా మీ బకాయిలను చెల్లించండి లేదా సహాయం కోసం మమ్మల్ని సంప్రదించండి.",
        "hi": "आपके पास वर्तमान में {count} EMI बकाया हैं। अपना स्टेटमेंट या भुगतान इतिहास डाउनलोड करने के लिए, कृपया पहले अपना बकाया चुकाएं, या सहायता के लिए हमसे संपर्क करें।",
        "kn": "ನಿಮಗೆ ಪ್ರಸ್ತುತ {count} EMI(ಗಳು) ಬಾಕಿ ಇವೆ. ನಿಮ್ಮ ಸ್ಟೇಟ್‌ಮೆಂಟ್ ಅಥವಾ ಪಾವತಿ ಇತಿಹಾಸವನ್ನು ಡೌನ್‌ಲೋಡ್ ಮಾಡಲು, ದಯವಿಟ್ಟು ಮೊದಲು ನಿಮ್ಮ ಬಾಕಿಯನ್ನು ತೀರಿಸಿ, ಅಥವಾ ಸಹಾಯಕ್ಕಾಗಿ ನಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    },
    "contact_required_seized_message": {
        "en": "Your vehicle has been repossessed as part of the recovery process. Statement, foreclosure statement, payment history, and receipt downloads are unavailable for this loan — please contact us to proceed further.",
        "te": "రికవరీ ప్రక్రియలో భాగంగా మీ వాహనం స్వాధీనం చేసుకోబడింది. ఈ రుణానికి స్టేట్‌మెంట్, ఫోర్‌క్లోజర్ స్టేట్‌మెంట్, చెల్లింపుల చరిత్ర మరియు రసీదు డౌన్‌లోడ్‌లు అందుబాటులో లేవు — దయచేసి కొనసాగడానికి మమ్మల్ని సంప్రదించండి.",
        "hi": "रिकवरी प्रक्रिया के तहत आपका वाहन जब्त कर लिया गया है। इस ऋण के लिए स्टेटमेंट, फोरक्लोज़र स्टेटमेंट, भुगतान इतिहास और रसीद डाउनलोड उपलब्ध नहीं हैं — आगे बढ़ने के लिए कृपया हमसे संपर्क करें।",
        "kn": "ರಿಕವರಿ ಪ್ರಕ್ರಿಯೆಯ ಭಾಗವಾಗಿ ನಿಮ್ಮ ವಾಹನವನ್ನು ವಶಪಡಿಸಿಕೊಳ್ಳಲಾಗಿದೆ. ಈ ಸಾಲಕ್ಕೆ ಸ್ಟೇಟ್‌ಮೆಂಟ್, ಫೋರ್‌ಕ್ಲೋಶರ್ ಸ್ಟೇಟ್‌ಮೆಂಟ್, ಪಾವತಿ ಇತಿಹಾಸ ಮತ್ತು ರಸೀದಿ ಡೌನ್‌ಲೋಡ್‌ಗಳು ಲಭ್ಯವಿಲ್ಲ — ಮುಂದುವರಿಯಲು ದಯವಿಟ್ಟು ನಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    },
    "whatsapp_us": {
        "en": "Chat with us on WhatsApp", "te": "WhatsApp లో మమ్మల్ని సంప్రదించండి",
        "hi": "WhatsApp पर हमसे चैट करें", "kn": "WhatsApp ನಲ್ಲಿ ನಮ್ಮೊಂದಿಗೆ ಚಾಟ್ ಮಾಡಿ",
    },
    "back_dashboard": {
        "en": "Back to dashboard", "te": "డాష్‌బోర్డ్‌కు తిరిగి",
        "hi": "डैशबोर्ड पर वापस जाएं", "kn": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗೆ ಹಿಂತಿರುಗಿ",
    },
    "helpline": {"en": "Helpline", "te": "హెల్ప్‌లైన్", "hi": "हेल्पलाइन", "kn": "ಸಹಾಯವಾಣಿ"},
    "grievance": {
        "en": "Grievance Redressal", "te": "ఫిర్యాదుల పరిష్కారం",
        "hi": "शिकायत निवारण", "kn": "ಕುಂದುಕೊರತೆ ಪರಿಹಾರ",
    },
    "ombudsman": {
        "en": "RBI Ombudsman", "te": "RBI అంబుడ్స్‌మన్", "hi": "RBI लोकपाल", "kn": "RBI ಒಂಬುಡ್ಸ್‌ಮನ್",
    },
    "fpc": {
        "en": "We follow the RBI Fair Practices Code. All charges are disclosed before payment.",
        "te": "మేము RBI ఫెయిర్ ప్రాక్టీసెస్ కోడ్‌ను పాటిస్తాము. చెల్లింపుకు ముందు అన్ని ఛార్జీలు తెలియజేయబడతాయి.",
        "hi": "हम RBI फेयर प्रैक्टिसेज़ कोड का पालन करते हैं। भुगतान से पहले सभी शुल्क बताए जाते हैं।",
        "kn": "ನಾವು RBI ನ್ಯಾಯಯುತ ಆಚರಣೆಗಳ ಸಂಹಿತೆಯನ್ನು ಅನುಸರಿಸುತ್ತೇವೆ. ಪಾವತಿಗೆ ಮೊದಲು ಎಲ್ಲಾ ಶುಲ್ಕಗಳನ್ನು ತಿಳಿಸಲಾಗುತ್ತದೆ.",
    },
    "session_expired": {
        "en": "Your session expired. Please login again.", "te": "మీ సెషన్ ముగిసింది. దయచేసి మళ్లీ లాగిన్ అవ్వండి.",
        "hi": "आपका सत्र समाप्त हो गया है। कृपया दोबारा लॉगिन करें।", "kn": "ನಿಮ್ಮ ಸೆಷನ್ ಅವಧಿ ಮುಗಿದಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಲಾಗಿನ್ ಆಗಿ.",
    },
    "no_loans": {
        "en": "No active loans found for this account.", "te": "ఈ ఖాతాకు యాక్టివ్ రుణాలు కనబడలేదు.",
        "hi": "इस खाते के लिए कोई सक्रिय ऋण नहीं मिला।", "kn": "ಈ ಖಾತೆಗೆ ಯಾವುದೇ ಸಕ್ರಿಯ ಸಾಲ ಕಂಡುಬಂದಿಲ್ಲ.",
    },
    # errors
    "err_mobile_not_found": {
        "en": "This mobile number is not registered with us.", "te": "ఈ మొబైల్ నంబర్ మా వద్ద నమోదు కాలేదు.",
        "hi": "यह मोबाइल नंबर हमारे पास पंजीकृत नहीं है।", "kn": "ಈ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ನಮ್ಮಲ್ಲಿ ನೋಂದಣಿಯಾಗಿಲ್ಲ.",
    },
    "err_invalid_mobile": {
        "en": "Please enter a valid 10-digit mobile number.", "te": "దయచేసి సరైన 10 అంకెల మొబైల్ నంబర్ నమోదు చేయండి.",
        "hi": "कृपया मान्य 10 अंकों का मोबाइल नंबर दर्ज करें।", "kn": "ದಯವಿಟ್ಟು ಮಾನ್ಯ 10 ಅಂಕಿಗಳ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ನಮೂದಿಸಿ.",
    },
    "err_agreement_not_found": {
        "en": "Agreement number and date of birth do not match our records.",
        "te": "అగ్రిమెంట్ నంబర్ మరియు పుట్టిన తేదీ మా రికార్డులతో సరిపోలడం లేదు.",
        "hi": "एग्रीमेंट नंबर और जन्म तिथि हमारे रिकॉर्ड से मेल नहीं खाते।",
        "kn": "ಒಪ್ಪಂದ ಸಂಖ್ಯೆ ಮತ್ತು ಹುಟ್ಟಿದ ದಿನಾಂಕ ನಮ್ಮ ದಾಖಲೆಗಳೊಂದಿಗೆ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ.",
    },
    "otp_rate_limited": {
        "en": "Too many OTP requests. Please try again after an hour.",
        "te": "చాలా OTP అభ్యర్థనలు. గంట తర్వాత మళ్లీ ప్రయత్నించండి.",
        "hi": "बहुत अधिक OTP अनुरोध। कृपया एक घंटे बाद पुनः प्रयास करें।",
        "kn": "ಹಲವಾರು OTP ವಿನಂತಿಗಳು. ದಯವಿಟ್ಟು ಒಂದು ಗಂಟೆಯ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    },
    "otp_resend_wait": {
        "en": "Please wait before requesting another OTP.", "te": "మరో OTP అడగడానికి ముందు కొంచెం వేచి ఉండండి.",
        "hi": "एक और OTP मांगने से पहले कृपया प्रतीक्षा करें।", "kn": "ಮತ್ತೊಂದು OTP ಕೇಳುವ ಮೊದಲು ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ.",
    },
    "otp_expired": {
        "en": "OTP expired. Please request a new one.", "te": "OTP గడువు ముగిసింది. కొత్తది అడగండి.",
        "hi": "OTP समाप्त हो गया है। कृपया नया मांगें।", "kn": "OTP ಅವಧಿ ಮುಗಿದಿದೆ. ದಯವಿಟ್ಟು ಹೊಸದನ್ನು ಕೇಳಿ.",
    },
    "otp_attempts_exhausted": {
        "en": "Too many wrong attempts. Please request a new OTP.", "te": "చాలా తప్పు ప్రయత్నాలు. కొత్త OTP అడగండి.",
        "hi": "बहुत अधिक गलत प्रयास। कृपया नया OTP मांगें।", "kn": "ಹಲವಾರು ತಪ್ಪು ಪ್ರಯತ್ನಗಳು. ದಯವಿಟ್ಟು ಹೊಸ OTP ಕೇಳಿ.",
    },
    "otp_not_found": {
        "en": "No active OTP. Please request one.", "te": "యాక్టివ్ OTP లేదు. దయచేసి అడగండి.",
        "hi": "कोई सक्रिय OTP नहीं है। कृपया मांगें।", "kn": "ಯಾವುದೇ ಸಕ್ರಿಯ OTP ಇಲ್ಲ. ದಯವಿಟ್ಟು ಕೇಳಿ.",
    },
    "otp_wrong": {
        "en": "Incorrect OTP. Please try again.", "te": "తప్పు OTP. మళ్లీ ప్రయత్నించండి.",
        "hi": "गलत OTP। कृपया पुनः प्रयास करें।", "kn": "ತಪ್ಪು OTP. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    },
    "pay_min_part": {
        "en": "Minimum part payment is ₹{amount}.", "te": "కనీస పాక్షిక చెల్లింపు ₹{amount}.",
        "hi": "न्यूनतम आंशिक भुगतान ₹{amount} है।", "kn": "ಕನಿಷ್ಠ ಭಾಗಶಃ ಪಾವತಿ ₹{amount}.",
    },
    "pay_exceeds_max": {
        "en": "Amount cannot exceed ₹{amount}.", "te": "మొత్తం ₹{amount} మించకూడదు.",
        "hi": "राशि ₹{amount} से अधिक नहीं हो सकती।", "kn": "ಮೊತ್ತ ₹{amount} ಮೀರಬಾರದು.",
    },
    "pay_bad_option": {
        "en": "Please choose a payment option.", "te": "దయచేసి చెల్లింపు ఎంపికను ఎంచుకోండి.",
        "hi": "कृपया भुगतान विकल्प चुनें।", "kn": "ದಯವಿಟ್ಟು ಪಾವತಿ ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ.",
    },
    "err_lms_down": {
        "en": "We are unable to reach the loan system right now. Please try again in a few minutes.",
        "te": "ప్రస్తుతం లోన్ సిస్టమ్‌ను చేరుకోలేకపోతున్నాము. కొన్ని నిమిషాల్లో మళ్లీ ప్రయత్నించండి.",
        "hi": "हम अभी लोन सिस्टम तक नहीं पहुंच पा रहे हैं। कृपया कुछ मिनटों में पुनः प्रयास करें।",
        "kn": "ನಾವು ಈಗ ಸಾಲ ವ್ಯವಸ್ಥೆಯನ್ನು ತಲುಪಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಕೆಲವು ನಿಮಿಷಗಳಲ್ಲಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    },
    "err_forbidden": {
        "en": "You do not have access to this loan.", "te": "ఈ రుణానికి మీకు యాక్సెస్ లేదు.",
        "hi": "आपको इस ऋण तक पहुंच नहीं है।", "kn": "ಈ ಸಾಲಕ್ಕೆ ನಿಮಗೆ ಪ್ರವೇಶವಿಲ್ಲ.",
    },
    "view_statement": {
        "en": "View statement", "te": "స్టేట్‌మెంట్ చూడండి",
        "hi": "स्टेटमेंट देखें", "kn": "ಸ್ಟೇಟ್‌ಮೆಂಟ್ ನೋಡಿ",
    },
    "view_foreclosure_statement": {
        "en": "View foreclosure statement", "te": "ఫోర్‌క్లోజర్ స్టేట్‌మెంట్ చూడండి",
        "hi": "फोरक्लोज़र स्टेटमेंट देखें", "kn": "ಫೋರ್‌ಕ್ಲೋಶರ್ ಸ್ಟೇಟ್‌ಮೆಂಟ್ ನೋಡಿ",
    },
    "view_receipt": {
        "en": "View receipt", "te": "రసీదు చూడండి",
        "hi": "रसीद देखें", "kn": "ರಸೀದಿ ನೋಡಿ",
    },
    "download_pdf": {"en": "Download PDF", "te": "PDF డౌన్‌లోడ్", "hi": "PDF डाउनलोड करें", "kn": "PDF ಡೌನ್‌ಲೋಡ್"},
    "statement_title": {
        "en": "Statement of Account", "te": "ఖాతా స్టేట్‌మెంట్",
        "hi": "खाता विवरण", "kn": "ಖಾತೆ ಹೇಳಿಕೆ",
    },
    "foreclosure_title": {
        "en": "Foreclosure Statement", "te": "ఫోర్‌క్లోజర్ స్టేట్‌మెంట్",
        "hi": "फोरक्लोज़र स्टेटमेंट", "kn": "ಫೋರ್‌ಕ್ಲೋಶರ್ ಸ್ಟೇಟ್‌ಮೆಂಟ್",
    },
    "payment_receipt_title": {
        "en": "Payment Receipt", "te": "చెల్లింపు రసీదు",
        "hi": "भुगतान रसीद", "kn": "ಪಾವತಿ ರಸೀದಿ",
    },
    "charges_title": {
        "en": "Charges Receipt", "te": "ఛార్జీల రసీదు",
        "hi": "शुल्क रसीद", "kn": "ಶುಲ್ಕ ರಸೀದಿ",
    },
    "borrower_details": {
        "en": "Borrower Details", "te": "రుణగ్రహీత వివరాలు",
        "hi": "उधारकर्ता विवरण", "kn": "ಸಾಲಗಾರರ ವಿವರಗಳು",
    },
    "repayment_schedule": {
        "en": "Repayment Schedule", "te": "చెల్లింపు షెడ్యూల్",
        "hi": "पुनर्भुगतान अनुसूची", "kn": "ಮರುಪಾವತಿ ವೇಳಾಪಟ್ಟಿ",
    },
    "guarantors": {"en": "Guarantor(s)", "te": "పూచీకత్తుదారు(లు)", "hi": "गारंटर", "kn": "ಖಾತರಿದಾರರು"},
    "relation": {"en": "Relation", "te": "సంబంధం", "hi": "संबंध", "kn": "ಸಂಬಂಧ"},
    "mobile_no": {"en": "Mobile No.", "te": "మొబైల్ నంబర్", "hi": "मोबाइल नंबर", "kn": "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ"},
    "col_due_date": {"en": "Due Date", "te": "గడువు తేదీ", "hi": "नियत तारीख", "kn": "ಬಾಕಿ ದಿನಾಂಕ"},
    "col_paid": {"en": "Paid", "te": "చెల్లించినది", "hi": "भुगतान किया गया", "kn": "ಪಾವತಿಸಲಾಗಿದೆ"},
    "col_last_paid": {
        "en": "Last Paid Date", "te": "చివరిగా చెల్లించిన తేదీ",
        "hi": "अंतिम भुगतान तिथि", "kn": "ಕೊನೆಯ ಪಾವತಿ ದಿನಾಂಕ",
    },
    "col_lpi_due": {"en": "LPI Due", "te": "LPI బకాయి", "hi": "LPI बकाया", "kn": "LPI ಬಾಕಿ"},
    "foreclosure_breakup": {
        "en": "Foreclosure Break-up", "te": "ఫోర్‌క్లోజర్ విభజన",
        "hi": "फोरक्लोज़र ब्यौरा", "kn": "ಫೋರ್‌ಕ್ಲೋಶರ್ ವಿವರ",
    },
    "total_receivables": {
        "en": "Total Receivables", "te": "మొత్తం రావలసినది",
        "hi": "कुल प्राप्य राशि", "kn": "ಒಟ್ಟು ಸ್ವೀಕರಿಸಬೇಕಾದ ಮೊತ್ತ",
    },
    "valid_until": {"en": "Valid Until", "te": "వరకు చెల్లుబాటు", "hi": "तक मान्य", "kn": "ವರೆಗೆ ಮಾನ್ಯ"},
    "foreclosure_validity_notice": {
        "en": "This foreclosure amount is valid only until the date above. If not settled within "
              "this period, a fresh statement must be requested.",
        "te": "ఈ ఫోర్‌క్లోజర్ మొత్తం పైన ఉన్న తేదీ వరకు మాత్రమే చెల్లుతుంది. ఈ వ్యవధిలో చెల్లించకపోతే, "
              "కొత్త స్టేట్‌మెంట్ కోసం అభ్యర్థించాలి.",
        "hi": "यह फोरक्लोज़र राशि केवल ऊपर दी गई तिथि तक ही मान्य है। इस अवधि में भुगतान न करने पर, "
              "नया स्टेटमेंट अनुरोध करना होगा।",
        "kn": "ಈ ಫೋರ್‌ಕ್ಲೋಶರ್ ಮೊತ್ತವು ಮೇಲಿನ ದಿನಾಂಕದವರೆಗೆ ಮಾತ್ರ ಮಾನ್ಯವಾಗಿರುತ್ತದೆ. ಈ ಅವಧಿಯೊಳಗೆ "
              "ಪಾವತಿಸದಿದ್ದರೆ, ಹೊಸ ಸ್ಟೇಟ್‌ಮೆಂಟ್ ಕೋರಬೇಕು.",
    },
    "fc_charges": {"en": "Fore-Closure Charges", "te": "ఫోర్-క్లోజర్ ఛార్జీలు", "hi": "फोर-क्लोज़र शुल्क", "kn": "ಫೋರ್-ಕ್ಲೋಶರ್ ಶುಲ್ಕ"},
    "future_principal": {
        "en": "Future Principal", "te": "భవిష్యత్ అసలు",
        "hi": "भविष्य की मूल राशि", "kn": "ಭವಿಷ್ಯದ ಅಸಲು",
    },
    "broken_interest": {
        "en": "Broken Period Interest", "te": "బ్రోకెన్ పీరియడ్ వడ్డీ",
        "hi": "ब्रोकन पीरियड ब्याज", "kn": "ಬ್ರೋಕನ್ ಪಿರಿಯಡ್ ಬಡ್ಡಿ",
    },
    "handloan": {"en": "Handloan", "te": "హ్యాండ్‌లోన్", "hi": "हैंडलोन", "kn": "ಹ್ಯಾಂಡ್‌ಲೋನ್"},
    "insurance": {"en": "Insurance", "te": "బీమా", "hi": "बीमा", "kn": "ವಿಮೆ"},
    "receipt_no": {"en": "Receipt No.", "te": "రసీదు నంబర్", "hi": "रसीद संख्या", "kn": "ರಸೀದಿ ಸಂಖ್ಯೆ"},
    "agreement_no_short": {"en": "Agreement No.", "te": "అగ్రిమెంట్ నంబర్", "hi": "एग्रीमेंट नंबर", "kn": "ಒಪ್ಪಂದ ಸಂಖ್ಯೆ"},
    "discount": {"en": "Discount", "te": "డిస్కౌంట్", "hi": "छूट", "kn": "ರಿಯಾಯಿತಿ"},
    "utr_ref": {"en": "UTR / Payment Ref", "te": "UTR / చెల్లింపు రిఫరెన్స్", "hi": "UTR / भुगतान संदर्भ", "kn": "UTR / ಪಾವತಿ ಉಲ್ಲೇಖ"},
    "payment_mode": {"en": "Payment Mode", "te": "చెల్లింపు విధానం", "hi": "भुगतान का तरीका", "kn": "ಪಾವತಿ ವಿಧಾನ"},
    "allocation_breakup": {
        "en": "Allocation Break-up", "te": "కేటాయింపు విభజన",
        "hi": "आवंटन ब्यौरा", "kn": "ಹಂಚಿಕೆ ವಿವರ",
    },
    "principal_emi": {
        "en": "EMI / Principal amount", "te": "EMI / అసలు మొత్తం",
        "hi": "EMI / मूल राशि", "kn": "EMI / ಅಸಲು ಮೊತ್ತ",
    },
    "total_received": {"en": "Total Received", "te": "మొత్తం అందుకున్నది", "hi": "कुल प्राप्त राशि", "kn": "ಒಟ್ಟು ಸ್ವೀಕರಿಸಿದ ಮೊತ್ತ"},
    "description": {"en": "Description", "te": "వివరణ", "hi": "विवरण", "kn": "ವಿವರಣೆ"},
    "bounce_charges": {"en": "Bounce Charges", "te": "బౌన్స్ ఛార్జీలు", "hi": "बाउंस शुल्क", "kn": "ಬೌನ್ಸ್ ಶುಲ್ಕ"},
    "other_charges": {"en": "Other Charges", "te": "ఇతర ఛార్జీలు", "hi": "अन्य शुल्क", "kn": "ಇತರ ಶುಲ್ಕ"},
    "no_charges_found": {
        "en": "No charges found for this date.", "te": "ఈ తేదీకి ఛార్జీలు కనుగొనబడలేదు.",
        "hi": "इस तिथि के लिए कोई शुल्क नहीं मिला।", "kn": "ಈ ದಿನಾಂಕಕ್ಕೆ ಯಾವುದೇ ಶುಲ್ಕಗಳು ಕಂಡುಬಂದಿಲ್ಲ.",
    },
    "system_generated_note": {
        "en": "This is a system-generated document and does not require a signature.",
        "te": "ఇది సిస్టమ్ ద్వారా రూపొందించిన పత్రం, సంతకం అవసరం లేదు.",
        "hi": "यह एक सिस्टम-जनित दस्तावेज़ है और इसके लिए हस्ताक्षर की आवश्यकता नहीं है।",
        "kn": "ಇದು ಸಿಸ್ಟಂ-ಜನಿತ ದಾಖಲೆಯಾಗಿದ್ದು, ಸಹಿಯ ಅಗತ್ಯವಿಲ್ಲ.",
    },
    "install_app_prompt": {
        "en": "Install this app on your phone for quick, one-tap access.",
        "te": "త్వరిత యాక్సెస్ కోసం ఈ యాప్‌ను మీ ఫోన్‌లో ఇన్‌స్టాల్ చేసుకోండి.",
        "hi": "तुरंत एक-टैप एक्सेस के लिए इस ऐप को अपने फ़ोन में इंस्टॉल करें।",
        "kn": "ತ್ವರಿತ ಪ್ರವೇಶಕ್ಕಾಗಿ ಈ ಆ್ಯಪ್ ಅನ್ನು ನಿಮ್ಮ ಫೋನ್‌ನಲ್ಲಿ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡಿ.",
    },
    "install": {"en": "Install", "te": "ఇన్‌స్టాల్", "hi": "इंस्टॉल करें", "kn": "ಇನ್‌ಸ್ಟಾಲ್"},
    "not_now": {"en": "Not now", "te": "ఇప్పుడు వద్దు", "hi": "अभी नहीं", "kn": "ಈಗ ಬೇಡ"},
}


def translate(key: str, lang: str = "en") -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get("en") or key


def make_translator(lang: str):
    return lambda key: translate(key, lang)
