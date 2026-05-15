// Simple i18n - Arabic + English translations
export const translations = {
  ar: {
    // Hero
    appName: 'X Posts Scraper',
    appTagline: 'استخراج آخر البوستات من حسابات X (Twitter)',
    badgeFast: '⚡ سريع',
    badgeAccurate: '🎯 دقيق',
    badgeSafe: '🛡️ آمن',
    badgeReliable: '📊 موثوق',

    // Search card
    searchTypeLabel: '🔎 نوع البحث',
    searchTypeUser: 'اسم حساب',
    searchTypeKeyword: 'كلمة مفتاحية',
    searchTypeHashtag: 'هاشتاج',
    queryLabelUser: 'اسم المستخدم (بدون @)',
    queryLabelKeyword: 'كلمات مفتاحية',
    queryLabelHashtag: 'الهاشتاج (بدون #)',
    queryPhUser: 'achetou_tah',
    queryPhKeyword: 'كأس العالم',
    queryPhHashtag: 'مونديال_قطر',
    enterQuery: 'من فضلك أدخل كلمة البحث',
    usernameLabel: 'اسم المستخدم (بدون @)',
    fromDate: '📅 من يوم',
    toDate: '📅 إلى يوم',
    postsCount: 'عدد البوستات',
    startBtn: '🔍 ابدأ الاستخراج',
    loadingBtn: '⏳ جاري الاستخراج...',

    // Loading / errors
    loadingText: 'جاري استخراج البوستات',
    enterUsername: 'من فضلك أدخل اسم المستخدم',
    noPosts: 'لم يتم العثور على بوستات في هذه الفترة',
    backendError: 'خطأ في الاتصال بـ Backend - تأكد أنه يعمل على المنفذ 8000',
    fetchFailed: 'تعذر جلب البوستات. حاول مرة أخرى.',

    // Results
    extracted: 'تم استخراج',
    post: 'بوست',
    downloadCsv: '📥 تحميل CSV',
    downloadExcel: '📊 تحميل Excel',

    // Sections
    sectionPosts: '📝 البوستات الأصلية',
    sectionRetweets: '🔁 إعادة التغريد والاقتباس',
    sectionVideos: '🎬 الفيديوهات',

    // Badges
    badgeVideo: '🎬 فيديو',
    badgeRetweet: '🔁 إعادة تغريد',
    badgeQuote: '💬 اقتباس',

    // Card actions
    openOnX: '🔗 فتح البوست على X',
    watchVideo: '▶️ مشاهدة الفيديو',

    // Stats tooltips
    statLikes: 'إعجابات',
    statComments: 'ردود',
    statRetweets: 'إعادة نشر',
    statViews: 'مشاهدات',

    // Analytics
    analyticsTitle: '📊 التحليل البياني للمخرجات',
    totalPosts: 'إجمالي البوستات',
    totalLikes: 'إجمالي الإعجابات',
    totalViews: 'إجمالي المشاهدات',
    totalComments: 'إجمالي الردود',
    totalRetweets: 'إجمالي إعادة النشر',
    engagementRate: 'معدل التفاعل',
    typeDistribution: 'توزيع البوستات حسب النوع',
    typeOriginal: 'بوستات أصلية',
    typeRetweets: 'إعادة تغريد/اقتباس',
    typeVideos: 'فيديوهات',
    topViews: 'أكثر البوستات مشاهدة (Top 5)',
    noText: 'بدون نص',
    averages: 'المتوسطات لكل بوست',
    avgLike: 'إعجاب / بوست',
    avgComment: 'رد / بوست',
    avgRetweet: 'إعادة نشر / بوست',
    avgView: 'مشاهدة / بوست',

    // Date dropdown sublabels
    today: 'اليوم',
    yesterday: 'أمس',
    daysAgo: (n, y) => `منذ ${n} يوم · ${y}`,
    periodFrom: (s, e) => `من ${s} إلى ${e}`,

    // Lang button
    langSwitch: 'EN',
    langSwitchLabel: 'English',
  },

  en: {
    appName: 'X Posts Scraper',
    appTagline: 'Extract the latest posts from X (Twitter) accounts',
    badgeFast: '⚡ Fast',
    badgeAccurate: '🎯 Accurate',
    badgeSafe: '🛡️ Safe',
    badgeReliable: '📊 Reliable',

    searchTypeLabel: '🔎 Search type',
    searchTypeUser: 'Username',
    searchTypeKeyword: 'Keyword',
    searchTypeHashtag: 'Hashtag',
    queryLabelUser: 'Username (without @)',
    queryLabelKeyword: 'Keywords',
    queryLabelHashtag: 'Hashtag (without #)',
    queryPhUser: 'achetou_tah',
    queryPhKeyword: 'World Cup',
    queryPhHashtag: 'WorldCup',
    enterQuery: 'Please enter a search term',
    usernameLabel: 'Username (without @)',
    fromDate: '📅 From',
    toDate: '📅 To',
    postsCount: 'Posts count',
    startBtn: '🔍 Start scraping',
    loadingBtn: '⏳ Scraping...',

    loadingText: 'Fetching posts',
    enterUsername: 'Please enter a username',
    noPosts: 'No posts found in this period',
    backendError: 'Connection error - make sure the backend runs on port 8000',
    fetchFailed: 'Failed to fetch posts. Please try again.',

    extracted: 'Extracted',
    post: 'posts',
    downloadCsv: '📥 Download CSV',
    downloadExcel: '📊 Download Excel',

    sectionPosts: '📝 Original posts',
    sectionRetweets: '🔁 Retweets & quotes',
    sectionVideos: '🎬 Videos',

    badgeVideo: '🎬 Video',
    badgeRetweet: '🔁 Retweet',
    badgeQuote: '💬 Quote',

    openOnX: '🔗 Open on X',
    watchVideo: '▶️ Watch video',

    statLikes: 'Likes',
    statComments: 'Replies',
    statRetweets: 'Retweets',
    statViews: 'Views',

    analyticsTitle: '📊 Analytics dashboard',
    totalPosts: 'Total posts',
    totalLikes: 'Total likes',
    totalViews: 'Total views',
    totalComments: 'Total replies',
    totalRetweets: 'Total retweets',
    engagementRate: 'Engagement rate',
    typeDistribution: 'Posts type distribution',
    typeOriginal: 'Original posts',
    typeRetweets: 'Retweets/Quotes',
    typeVideos: 'Videos',
    topViews: 'Top 5 most viewed posts',
    noText: 'No text',
    averages: 'Averages per post',
    avgLike: 'Like / post',
    avgComment: 'Reply / post',
    avgRetweet: 'Retweet / post',
    avgView: 'View / post',

    today: 'Today',
    yesterday: 'Yesterday',
    daysAgo: (n, y) => `${n} days ago · ${y}`,
    periodFrom: (s, e) => `From ${s} to ${e}`,

    langSwitch: 'ع',
    langSwitchLabel: 'العربية',
  },
}
