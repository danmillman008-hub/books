# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, '.')
import tgsearch as T

FIX = '''
<div class="tgme_channel_info_header_title"><span dir="auto">Ensaniha</span></div>
<div class="tgme_channel_info_header_username"><a href="https://t.me/ensaniha">@ensaniha</a></div>
<div class="tgme_channel_info_description">محلی برای ارتقا دانش رشته علوم انسانی<br/>توسط وحید تمنا</div>
<div class="tgme_channel_info_counters">
<div class="tgme_channel_info_counter"><span class="counter_value">777</span><span class="counter_type">subscribers</span></div>
<div class="tgme_channel_info_counter"><span class="counter_value">432</span><span class="counter_type">files</span></div>
<div class="tgme_channel_info_counter"><span class="counter_value">3.7K</span><span class="counter_type">photos</span></div>
<div class="tgme_channel_info_counter"><span class="counter_value">1.63K</span><span class="counter_type">links</span></div>
</div>

<div class="tgme_widget_message_wrap js-widget_message_wrap">
<div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="ensaniha/8968">
<div class="tgme_widget_message_text js-message_text"><a href="?q=%23%DA%A9%D9%86%DA%A9%D9%88%D8%B1">#کنکور</a> <a href="?q=x">#برنامه_ریزی_هفتگی</a><br/>&#1583;&#1608;&#1587;&#1578;&#1575;&#1606; عزیز یازدهمی!<br/>از <b>برنامه مطالعاتی</b> هفته به هفته استفاده کنید: <a href="http://www.ensaniha.ir/post/index/5342">سایت</a></div>
<div class="tgme_widget_message_footer compact js-message_footer">
<span class="tgme_widget_message_views">4K</span>
<a class="tgme_widget_message_date" href="https://t.me/ensaniha/8968"><time datetime="2020-11-20T13:50:12+00:00"></time></a>
</div>
</div>
</div>

<div class="tgme_widget_message_wrap js-widget_message_wrap">
<div class="tgme_widget_message js-widget_message" data-post="ensaniha/8978">
<div class="tgme_widget_message_document_wrap accent_bg">
<div class="tgme_widget_message_document">
<div class="tgme_widget_message_document_title accent_color">برنامه_مطالعاتی_هفته_سوم_پایه_دهم.pdf</div>
<div class="tgme_widget_message_document_extra">776 KB</div>
</div>
</div>
<div class="tgme_widget_message_text js-message_text">#دهم_انسانی برنامه هفته سوم</div>
<div class="tgme_widget_message_footer compact js-message_footer">
<span class="tgme_widget_message_views">5.03K</span>
<a class="tgme_widget_message_date" href="https://t.me/ensaniha/8978"><time datetime="2020-12-06T14:41:00+00:00"></time></a>
</div>
</div>
</div>

<div class="tgme_widget_message_wrap js-widget_message_wrap">
<div class="tgme_widget_message js-widget_message" data-post="ensaniha/9001">
<a class="tgme_widget_message_photo_wrap" style="background-image:url(&#39;https://cdn4.telesco.pe/file/abc.jpg&#39;)"></a>
<div class="tgme_widget_message_document_wrap accent_bg">
<div class="tgme_widget_message_document">
<div class="tgme_widget_message_document_title accent_color">گزارش_کار_هفتگی.zip</div>
<div class="tgme_widget_message_document_extra">1.2 MB</div>
</div>
</div>
<div class="tgme_widget_message_text js-message_text">فرم گزارش کار</div>
<div class="tgme_widget_message_footer compact js-message_footer">
<a class="tgme_widget_message_date" href="https://t.me/ensaniha/9001"><time datetime="2021-01-02T10:00:00+00:00"></time></a>
</div>
</div>
</div>

<a class="tme_messages_more js-messages_more" data-before="8968" href="/s/ensaniha?before=8968">Load more</a>
'''

info = T.parse_channel_info(FIX)
posts = T.parse_posts(FIX)
nb = T.next_before(FIX)

ok = True
def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(("  ✓ " if good else "  ✗ ") + label + f"  got={got!r}" + ("" if good else f" want={want!r}"))

print("info:")
chk("title", info["title"], "Ensaniha")
chk("username", info["username"], "ensaniha")
chk("subscribers", info["subscribers"], "777")
chk("files", info["files"], "432")
chk("desc has وحید", "وحید تمنا" in info["description"], True)

print("posts:")
chk("count", len(posts), 3)
chk("p0 id", posts[0]["id"], "ensaniha/8968")
chk("p0 url", posts[0]["url"], "https://t.me/ensaniha/8968")
chk("p0 date", posts[0]["date"][:10], "2020-11-20")
chk("p0 views", posts[0]["views"], "4K")
chk("p0 entity decoded", "دوستان" in posts[0]["text"], True)
chk("p0 tags", posts[0]["tags"], ["#کنکور", "#برنامه_ریزی_هفتگی"])
chk("p0 ext link", "http://www.ensaniha.ir/post/index/5342" in posts[0]["links"], True)
chk("p0 no docs", posts[0]["docs"], [])

chk("p1 doc name", posts[1]["docs"][0]["name"], "برنامه_مطالعاتی_هفته_سوم_پایه_دهم.pdf")
chk("p1 doc size", posts[1]["docs"][0]["size"], "776 KB")
chk("p2 doc name", posts[2]["docs"][0]["name"], "گزارش_کار_هفتگی.zip")
chk("p2 media", posts[2]["media"], ["https://cdn4.telesco.pe/file/abc.jpg"])

print("pagination:")
chk("before", nb, "8968")

print("\nرندر markdown فایل‌ها:")
rows = [(d["name"], d["size"], p["url"]) for p in posts for d in p["docs"]]
chk("file rows", len(rows), 2)
print(T.md_posts(posts[1:2], limit_chars=80))

print("\n" + ("✅ همهٔ تست‌ها پاس شد" if ok else "❌ تست شکست خورد"))
sys.exit(0 if ok else 1)
