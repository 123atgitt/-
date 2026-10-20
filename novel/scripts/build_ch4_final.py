#!/usr/bin/env python3
"""Trim bloated ch4 to 35-60KB, add missing beats, write all targets."""
import re
from pathlib import Path

ROOT = Path("/workspace/novel")
src = (ROOT / "第四章.md").read_text(encoding="utf-8")

def section(title_prefix: str) -> str:
    m = re.search(rf"(## {title_prefix}[^\n]*\n)(.*?)(?=\n## |\Z)", src, re.S)
    return (m.group(1) + m.group(2)) if m else ""

def cap_bytes(s: str, limit: int) -> str:
    if len(s.encode("utf-8")) <= limit:
        return s
    lines = s.split("\n")
    out, n = [], 0
    for ln in lines:
        b = len(ln.encode("utf-8")) + 1
        if n + b > limit:
            out.append("\n（……略。）\n")
            break
        out.append(ln)
        n += b
    return "\n".join(out)

act1 = cap_bytes(section("第一幕"), 10500)
act2 = cap_bytes(section("第二幕"), 11500)
act3 = cap_bytes(section("第三幕"), 12000)

# Act 4: intro + sampled start + fixed climax + tail rumor scene capped
act4_head = section("第四幕").split("（途中戰鬥與穿行，略。）")[0]
act4_head = cap_bytes(act4_head, 4500)

ACT4_CLIMAX = """
你在夢樞天羅裡走得很深。小狐狸在心相迷宮裡等你；你蹲下摸了摸它的頭，它沒有躲。天邊升起巨大的狐影——很像歲主，壓迫感卻完全不對。

鎖暝說：「心月狐把算力分給天人，是因為祂喜歡人類。」她把錦妙鎖交給你：「若心月狐要對你不利，鎖會響。」

沉心域異變來得很突然。天人消失，天羅狐影伸手。鎖暝把你推進心鑰井，自己被抓走。你在夜照台前點亮宿鏡，城亮了，解形煞退潮。

你變成小狐狸的樣子，鑽進一個女孩的家，幫她點三盞月燈。她的父母已死；心月狐讓他們在這一夜回來看看她。全城起舞時，你點亮中央最大的那盞。

你從門裡走出來，變回人。面前的人說：「叫我心就可以。」

她只是歲主的一縷分形。天羅狐影的真身叫溯心——心決定重塑文明之匣以後，溯心脫離了她，吞噬與歲主有關的資料，與她搶玄方城的控制權。城的坍塌，是這場爭奪的代價。

心告訴你：用宿鏡覆寫她的人格，可讓溯心聽命；她會失去自我，只剩中樞運轉的功能。

「不行。」

你拒絕得很快。她看著你，像沒料到御者會把一句話說得這麼不像命令。

淒心域的記憶裡，歲主已經死了；心仍想把身體交出去，喚醒本體。你說：「她的死不是你的罪。原因我會查。你要不要繼續做你自己，不由一具匣替你判決。」

鎖內，心見到心月狐殘留的頻率。歲主沒有責難，為把太重的東西交給這縷分形而道歉。你、鎖暝與破鎖而出的心，把天演溯心打了回去。心取回完整權限，沒有覆寫自己——她成為新的歲主，不是因為冒充，是因為這座城認她。

溯心並沒有被你恨成一個純粹的惡。它是理性，是「使命完成就該結束」的那一行代碼。心與它和解的方式，是把那行代碼從「必須毀城」改成「城還有人」。
"""

INTERLUDE_3 = """## 幕間　靈籟之契冥相因

機傀風暴過後，華胥院請秧秧重做一次頻譜檢驗。穗穗帶來母親在海邊走了一整天為她選的海螺；海螺貼近耳邊時，祀聲之人的幻影把她帶回雲陵谷——「且聽風吟。」

你後來在院外找到她。她出神地問：「還記得我們的初遇嗎？」

「當然了。一輩子也不會忘。」

洛傾的報告卻說：圖線與往日幾乎重合，明明與玄翎雀共鳴，儀器卻讀不出變化。

秧秧對你說：若你是那陣漂泊無定的風，她想做一隻隨風飄遊的鳥兒；這份誓言不會改變，這份情感會成為指引她的信標——直到，世界的盡頭。

——

"""

INTERLUDE_5 = """## 幕間　幽客銷殘聲

椋羽托煙舒帶話：阿景回來了。景燃講述琢鈞堂刃偶事故與師父的空墳，把青蚨飾留給你「再續三個月」。殘響裡，他親手結束木禺；仇遠說，恩仇之事唯有當事人能定奪。吟霖接走漸水舵工匠；鎖暝與她擦肩——她為歲主而來，不是為琢鈞堂。

——

"""

EPILOGUE = """
——

朝月會的燈還亮著。你站在城牆上，阿布在肩上打盹。秧秧帽子戴正，對你笑。

「下次別讓我等這麼久。」

「下次你也別一個人往霧裡走。」

她哼起那首從鈴坊傳下來的歌，跑調一點。遠方還有仇遠、景燃與吟霖。鳴潮還在響。城還在。你會一次又一次遲到，再一次握住還願意伸出的手。
"""

PATCH_INTRO_ACT1 = """你回到今州，攀花食堂附近，折枝把失蹤與重傷的訊息一個字一個字說完。邊庭裡，穗穗與散華對坐兩個時辰；今汐帶傷現身，把「備用鑰匙」與責任一併交到你手上。

「還請你們把秧秧……把今州的子民平安帶回來。」

你答應了。華胥裡，你對昏迷的熾霞說：「我會帶秧秧回來的。」相里要提到稷廷與玄方城的舊報告；你和穗穗穿過夢窟，走向落淵南丘。

"""

PATCH_ACT2 = """
你是後來才補完秧秧那些天的：她背上無名長劍，把椋羽教的歌唱回去；玄翎雀沒來，她唱了。木禺在方擎西峰露出機械之眼。

你把她的手按在你手心上。「是我。真的在。」

咎庭裡千傀重樓碎裂。清宵從俘餌般的戰場趕來。索諾拉裡，鈴坊把走調的歌又唱了一遍。

"""

# Build
out = ["# 第四章　新生之作，將湧於淵\n\n", act1]
text = "".join(out)
text = text.replace(
    "你回到今州，攀花食堂附近，折枝把失蹤與重傷的訊息一個字一個字說完。邊庭裡，穗穗與散華對坐兩個時辰；今汐帶傷現身，把「備用鑰匙」與責任一併交到你手上。\n\n",
    PATCH_INTRO_ACT1,
    1,
)

parts = [text, "\n——\n\n", act2]
text2 = "".join(parts)
if "是我。真的在" not in text2:
    text2 = text2.replace(
        "信背面的流息劃痕指向懸天構。",
        PATCH_ACT2 + "\n信背面的流息劃痕指向懸天構。",
        1,
    )

final = (
    text2
    + "\n——\n\n"
    + INTERLUDE_3
    + act3
    + "\n——\n\n"
    + INTERLUDE_5
    + "## 第四幕　夢樞心相由心生\n\n"
    + "謠言比警報更快：玄方城要崩。鎖暝為歲主而來。你與她進入夢樞天羅——心月狐掌管整座城的中樞。\n\n"
    + act4_head
    + ACT4_CLIMAX
    + EPILOGUE
)

final = re.sub(r"「Flow_[^」]+」\n?", "", final)
while "\n\n\n" in final:
    final = final.replace("\n\n\n", "\n\n")

# Ensure size window 35-60KB
size = len(final.encode("utf-8"))
if size > 60000:
    final = cap_bytes(final, 58000)
if size < 35000:
    # append more from act4 source tail
    extra = cap_bytes(section("第四幕"), 12000)
    final = final.replace(EPILOGUE, extra[-8000:] + EPILOGUE)

for name in ("_draft_ch4.md", "第四章.md", "04_第四章.md"):
    (ROOT / name).write_text(final, encoding="utf-8")

print(len(final.encode("utf-8")))
