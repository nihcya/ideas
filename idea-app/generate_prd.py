#!/usr/bin/env python3
"""点子 App PRD V1.0 - ReportLab Body Generator"""

import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'pdf', 'scripts'))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, CondPageBreak, HRFlowable
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ─── Fonts ───
pdfmetrics.registerFont(TTFont('LXGW', '/usr/share/fonts/truetype/lxgw-wenkai/LXGWWenKai-Regular.ttf'))
pdfmetrics.registerFont(TTFont('LXGW-Bold', '/usr/share/fonts/truetype/lxgw-wenkai/LXGWWenKai-Medium.ttf'))
pdfmetrics.registerFont(TTFont('SarasaMonoSC', '/usr/share/fonts/truetype/chinese/SarasaMonoSC-Regular.ttf'))
registerFontFamily('LXGW', normal='LXGW', bold='LXGW-Bold')
registerFontFamily('LXGW-Bold', normal='LXGW-Bold', bold='LXGW-Bold')

# ─── Palette ───
ACCENT       = colors.HexColor('#28718a')
TEXT_PRIMARY  = colors.HexColor('#171614')
TEXT_MUTED    = colors.HexColor('#7d7b73')
BG_SURFACE    = colors.HexColor('#ecebe8')
BG_PAGE       = colors.HexColor('#f4f4f3')
HEADER_FILL   = colors.HexColor('#706647')
BORDER_COLOR  = colors.HexColor('#d8d3c4')

TABLE_HEADER_COLOR = HEADER_FILL
TABLE_HEADER_TEXT  = colors.white
TABLE_ROW_EVEN     = colors.white
TABLE_ROW_ODD      = BG_SURFACE

# ─── Styles ───
W, H = A4
left_m = 1.0 * inch
right_m = 1.0 * inch
avail_w = W - left_m - right_m

h1_style = ParagraphStyle('H1', fontName='LXGW-Bold', fontSize=20, leading=28,
    textColor=ACCENT, spaceBefore=24, spaceAfter=12, wordWrap='CJK')
h2_style = ParagraphStyle('H2', fontName='LXGW-Bold', fontSize=15, leading=22,
    textColor=TEXT_PRIMARY, spaceBefore=18, spaceAfter=8, wordWrap='CJK')
h3_style = ParagraphStyle('H3', fontName='LXGW-Bold', fontSize=12, leading=18,
    textColor=ACCENT, spaceBefore=12, spaceAfter=6, wordWrap='CJK')
body_style = ParagraphStyle('Body', fontName='LXGW', fontSize=10.5, leading=17,
    textColor=TEXT_PRIMARY, spaceBefore=0, spaceAfter=8, wordWrap='CJK', alignment=TA_LEFT)
bullet_style = ParagraphStyle('Bullet', fontName='LXGW', fontSize=10.5, leading=17,
    textColor=TEXT_PRIMARY, spaceBefore=2, spaceAfter=4, wordWrap='CJK', alignment=TA_LEFT,
    leftIndent=20, bulletIndent=8)
muted_style = ParagraphStyle('Muted', fontName='LXGW', fontSize=9.5, leading=15,
    textColor=TEXT_MUTED, spaceBefore=2, spaceAfter=6, wordWrap='CJK')
code_style = ParagraphStyle('Code', fontName='SarasaMonoSC', fontSize=9, leading=14,
    textColor=TEXT_PRIMARY, spaceBefore=4, spaceAfter=8, leftIndent=12, wordWrap='CJK')
table_header_style = ParagraphStyle('TH', fontName='LXGW-Bold', fontSize=10,
    textColor=colors.white, alignment=TA_CENTER, leading=14)
table_cell_style = ParagraphStyle('TC', fontName='LXGW', fontSize=9.5,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT, leading=14, wordWrap='CJK')
table_cell_center = ParagraphStyle('TCC', fontName='LXGW', fontSize=9.5,
    textColor=TEXT_PRIMARY, alignment=TA_CENTER, leading=14, wordWrap='CJK')

# ─── TOC ───
class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, 'bookmark_name'):
            level = getattr(flowable, 'bookmark_level', 0)
            text = getattr(flowable, 'bookmark_text', '')
            key = getattr(flowable, 'bookmark_key', '')
            self.notify('TOCEntry', (level, text, self.page, key))

def add_heading(text, style, level=0):
    key = 'h_%s' % hashlib.md5(text.encode()).hexdigest()[:8]
    p = Paragraph('<a name="%s"/>%s' % (key, text), style)
    p.bookmark_name = text
    p.bookmark_level = level
    p.bookmark_text = text
    p.bookmark_key = key
    return p

# ─── Helper: Standard Table ───
def make_table(data, col_ratios=None, col_widths=None):
    if col_ratios:
        col_widths = [r * avail_w for r in col_ratios]
    elif not col_widths:
        col_widths = [avail_w / len(data[0])] * len(data[0])
    # Wrap all cells in Paragraph
    wrapped = []
    for i, row in enumerate(data):
        wrapped_row = []
        for j, cell in enumerate(row):
            if isinstance(cell, str):
                style = table_header_style if i == 0 else table_cell_style
                wrapped_row.append(Paragraph(cell, style))
            else:
                wrapped_row.append(cell)
        wrapped.append(wrapped_row)
    t = Table(wrapped, colWidths=col_widths, hAlign='CENTER')
    style_cmds = [
        ('BACKGROUND', (0,0), (-1,0), TABLE_HEADER_COLOR),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]
    for i in range(2, len(data), 2):
        style_cmds.append(('BACKGROUND', (0,i), (-1,i), TABLE_ROW_ODD))
    t.setStyle(TableStyle(style_cmds))
    return t

def hr():
    return HRFlowable(width='100%', thickness=0.5, color=BORDER_COLOR, spaceBefore=6, spaceAfter=6)

def bullet(text):
    return Paragraph('&bull; ' + text, bullet_style)

# ─── Build Story ───
story = []

# === TOC ===
toc = TableOfContents()
toc.levelStyles = [
    ParagraphStyle('TOC1', fontName='LXGW-Bold', fontSize=13, leading=20, leftIndent=10, textColor=TEXT_PRIMARY),
    ParagraphStyle('TOC2', fontName='LXGW', fontSize=11, leading=16, leftIndent=30, textColor=TEXT_MUTED),
]
story.append(Paragraph('<b>目录</b>', ParagraphStyle('TOCTitle', fontName='LXGW-Bold', fontSize=22, leading=30, textColor=ACCENT, spaceAfter=20)))
story.append(toc)
story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 1: Product Overview
# ═══════════════════════════════════════════
story.append(add_heading('一、产品概述', h1_style, level=0))
story.append(Paragraph('点子是一款基于创造力科学研究的手机App，通过圆圈随机分布的视觉语言、点子谱系图（GitHub for Ideas）的开源精神、以及碰撞与演化的AI辅助机制，激发用户产生新思路与新点子。', body_style))

story.append(add_heading('1.1 产品定位', h2_style, level=1))
story.append(make_table([
    ['维度', '定义'],
    ['产品名称', '点子'],
    ['核心承诺', '激发用户产生新思路和新点子'],
    ['产品形态', '内容平台（UGC 60% + PGC 40%），非纯工具'],
    ['社交属性', '公开全开放，面向"开源精神"创意社群'],
    ['内容所有权', '默认全公开，先做极端版，后续按反馈加私密选项'],
    ['商业模式', '订阅制（暂定），先开发不上线，社群测试后再定'],
    ['目标用户', '创意工作者/创业者/设计师/写作者/教育者/热心生活创意的人'],
    ['社群愿景', '"创意、分享和实现"的聚落'],
], col_ratios=[0.25, 0.75]))

story.append(add_heading('1.2 核心价值主张', h2_style, level=1))
story.append(Paragraph('现有产品分两派：AI直接给答案派（用户被动接收，创造力未被激发）与协作白板/固定卡牌派（太重或无个性化）。中间留白：轻量、个人化、基于创造力科学研究的"激发式"App。点子App填此空白。', body_style))

story.append(add_heading('1.3 科学研究基础', h2_style, level=1))
story.append(make_table([
    ['科学机制', '产品化方式', '研究来源'],
    ['随机刺激', '圆圈大小不一随机分布 + 颜色真随机 + 内容不预览', 'ScienceDirect 2021'],
    ['心智游走/淋浴效应', '演化菜单步行体验 + 震动反馈 + 草稿自动保存', 'APA PsycNet 2023'],
    ['跨域类比', '碰撞机制：两个不相关点子AI生成结合方案', 'EconStor'],
    ['发散+收敛双阶段', '双引擎：浏览发散 + 联想收敛产生自己的点子', 'OECD PISA'],
    ['约束激发创意', '300字限制 + 今日一点3分钟倒计时 + 后期次数限制', '经典研究'],
], col_ratios=[0.25, 0.50, 0.25]))

story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 2: Design Philosophy
# ═══════════════════════════════════════════
story.append(add_heading('二、设计哲学', h1_style, level=0))

story.append(add_heading('2.1 "没有烂点子"共识', h2_style, level=1))
story.append(Paragraph('一个人的烂点子可能是另一个人的好点子。这一共识是系列设计决策的源头：', body_style))
story.append(bullet('不做"踩/差评"功能'))
story.append(bullet('不做内容质量分级（PGC/UGC平等展示）'))
story.append(bullet('不做"优质点子"筛选算法'))
story.append(bullet('"热门"只是"被fork多的客观描述"，不是"好"的评价'))
story.append(Paragraph('<b>边界：</b>违规内容（广告/辱骂/抄袭）仍需审核机制，按照互联网治理标准和违禁词公开标准走AI审核。', muted_style))

story.append(add_heading('2.2 开源精神：点子谱系图', h2_style, level=1))
story.append(Paragraph('"开源精神"不能停留在口号，必须落地为机制。核心创新：让点子像代码一样可fork、可merge、可追溯出处。', body_style))
story.append(make_table([
    ['机制', '说明', '产品意义'],
    ['Fork（衍生）', '用户B基于A的点子写变体，自动标注forked from A，A收到通知', '被fork是荣誉而非损失'],
    ['Merge（碰撞）', '两个点子碰撞产生新点子，记录两个父节点', '产品化"跨域类比"科学机制'],
    ['Lineage（谱系树）', '每个点子详情页下方有家族树：祖先-它-后代', '贡献永久被记录，开源精神视觉化'],
], col_ratios=[0.20, 0.45, 0.35]))
story.append(Paragraph('<b>护城河：</b>其他App的点子是孤立的，点子App的点子有血脉。用户有"在创意谱系中留下印记"的归属感——比积分/勋章更高级的留存驱动。', body_style))

story.append(add_heading('2.3 创意激发 vs 信息消费', h2_style, level=1))
story.append(Paragraph('加type/tag的App = 信息消费App（用户来"找科技点子"）。不加type/tag的App = 创意激发App（用户被迫面对不熟悉的领域）。点子App选择后者——不分类不贴标，点子回归到纯粹的元素。', body_style))

story.append(add_heading('2.4 双引擎模型', h2_style, level=1))
story.append(make_table([
    ['引擎', '流程', '科学依据'],
    ['A 被动激发', '浏览圆圈 - 点击展开 - "这条让你想到什么？" - 联想 - 自己的点子', '随机刺激 + 跨域类比'],
    ['B 主动激发', '"今日一点"入口 - 每日一题 - 3分钟倒计时 - 写下想法 - 自己的点子', '约束激发 + 发散思维'],
], col_ratios=[0.15, 0.60, 0.25]))

story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 3: Feature Specs
# ═══════════════════════════════════════════
story.append(add_heading('三、功能规格（9个页面）', h1_style, level=0))

story.append(add_heading('3.1 主页（探索）', h2_style, level=1))
story.append(bullet('圆圈大小不一随机分布，无文字预览（方案C）'))
story.append(bullet('构成：90%随机 + 10%热门（近30天fork数Top，滚动窗口每日重算）'))
story.append(bullet('圆圈大小 = f(fork数, 近期fork衰减)'))
story.append(bullet('颜色 = 12-16色池真随机，与内容完全解耦'))
story.append(bullet('点击圆圈 - 跳详情页'))
story.append(bullet('顶栏：Logo + 发布按钮（+号）'))
story.append(bullet('底部Tab：探索/仓库/一点/我'))

story.append(add_heading('3.2 点子仓库', h2_style, level=1))
story.append(bullet('圆圈随机分布，与主页视觉一致'))
story.append(bullet('金色细边框 = 自己产生的点子；无边框 = 收集的别人的点子'))
story.append(bullet('统计条：产生数 / 收集数 / 被fork数'))
story.append(bullet('点击圆圈 - 跳详情页'))
story.append(bullet('点击圆圈弹出演化菜单（碰撞/演化）+ 步行震动反馈'))
story.append(bullet('自然淡出：一周未触碰的圆圈慢慢变小变淡，一周后移出仓库'))

story.append(add_heading('3.3 今日一点', h2_style, level=1))
story.append(bullet('每日一题（随机词/类比题/约束题/反向提问）'))
story.append(bullet('3分钟倒计时，时间约束激发创意'))
story.append(bullet('300字输入框，字数计数'))
story.append(bullet('倒计时结束自动保存草稿，可继续写'))
story.append(bullet('错过当日不能补做（强化稀缺性）'))
story.append(bullet('草稿保留到当日23:59，第一次保存时弹窗说明'))
story.append(bullet('提交后入仓库为金边圆圈'))

story.append(add_heading('3.4 点子详情页（含谱系图）', h2_style, level=1))
story.append(bullet('圆圈色块（与列表颜色一致）'))
story.append(bullet('点子文本（300字以内）'))
story.append(bullet('作者信息（点击进个人主页）+ 被fork数'))
story.append(bullet('两个主操作：Fork这个点子 / 收集'))
story.append(bullet('谱系图：父节点 - 当前 - 子节点（初期2层，后期完整树）'))
story.append(bullet('点Fork - 进入联想引导页'))
story.append(bullet('点谱系图中的圆圈 - 跳那个点子的详情页'))

story.append(add_heading('3.5 个人主页（公开视图）', h2_style, level=1))
story.append(Paragraph('<b>核心理念：</b>进入一片森林，而非攀爬一棵树。', body_style))
story.append(bullet('显示该用户仓库所有点子（自己产生的金边 + 收集的无边）'))
story.append(bullet('只看自己产生 = 沿fork回溯一条血脉线（窄）'))
story.append(bullet('看所有 = "思想食物 + 思想产物"生态（宽）'))
story.append(bullet('头像 + 昵称 + 一句话简介 + 统计（产生/被fork/fork别人）'))
story.append(bullet('与点子谱系图正交互补：谱系图=纵向家族树，个人主页=横向思维森林'))

story.append(add_heading('3.6 发布点子', h2_style, level=1))
story.append(bullet('从主页+号进入'))
story.append(bullet('300字输入框，字数计数'))
story.append(bullet('颜色系统自动随机分配，用户不可选'))
story.append(bullet('无type无tag可选，点子是纯粹元素'))
story.append(bullet('发布后入仓库为金边圆圈'))

story.append(add_heading('3.7 Fork联想引导', h2_style, level=1))
story.append(bullet('从详情页Fork按钮进入'))
story.append(bullet('显示原点子（只读）'))
story.append(bullet('提示："这条点子让你想到什么？"'))
story.append(bullet('300字输入框，字数计数'))
story.append(bullet('提交后：新点子入仓库（金边）+ 自动建立fork关系 + 通知原作者'))

story.append(add_heading('3.8 演化菜单（碰撞+演化）', h2_style, level=1))
story.append(Paragraph('<b>交互方式：</b>点击圆圈触发（非长按），漫游式路径展开 + 轻微震动反馈，模拟步行体验。科学依据：心智游走/淋浴效应——身体微动 + 心智游走 = 激发创造力。', body_style))
story.append(make_table([
    ['操作', '输入', 'AI输出', '科学依据'],
    ['碰撞', '2个点子', '3个结合方案（实用型/跨界型/反常规型）', '跨域类比'],
    ['演化', '1个点子 + SAMPER角度', '3个变体（近/中/远）', '经典创意技法'],
], col_ratios=[0.12, 0.28, 0.35, 0.25]))
story.append(Paragraph('<b>SAMPER 6角度</b>（去掉C=Combine，已由碰撞承担）：', body_style))
story.append(bullet('S - Substitute（替代）：这个点子里什么可以被替换？'))
story.append(bullet('A - Adapt（适应）：能从其他领域借鉴什么？'))
story.append(bullet('M - Modify（修改）：放大或缩小某个方面？'))
story.append(bullet('P - Put to other use（其他用途）：这个点子还能用在哪里？'))
story.append(bullet('E - Eliminate（消除）：去掉什么会让它更好？'))
story.append(bullet('R - Reverse（反转）：反过来想会怎样？'))
story.append(Paragraph('<b>每日次数限制：</b>MVP不限制，后期建立成本模型根据AI调用成本限制。科学依据：约束激发创意——行为约束也激发创造力。', muted_style))

story.append(add_heading('3.9 通知与设置', h2_style, level=1))
story.append(bullet('通知页：被fork通知 / 被收集通知 / 今日一点更新提醒'))
story.append(bullet('设置页：账号 / 暗色模式 / forkable开关（默认开）/ 退出'))

story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 4: Visual Specs
# ═══════════════════════════════════════════
story.append(add_heading('四、视觉规范', h1_style, level=0))

story.append(add_heading('4.1 圆圈设计系统', h2_style, level=1))
story.append(make_table([
    ['维度', '编码方式', '说明'],
    ['热度', '大小', 'fork数 + 近期衰减；唯一热度指标'],
    ['随机刺激', '颜色', '12-16色池真随机，与内容完全解耦'],
    ['自己/别人', '边框', '金色细边框=自己产生；无边框=收集的'],
    ['内容预览', '无', '方案C：圆圈不显示任何文字，强制点开看'],
], col_ratios=[0.20, 0.15, 0.65]))

story.append(add_heading('4.2 色彩规则', h2_style, level=1))
story.append(bullet('12-16色池，明度饱和度都有变化（太少成"伪分类"，太多视觉混乱）'))
story.append(bullet('真随机分配，禁止按内容哈希（否则又成隐藏分类）'))
story.append(bullet('用户应能发现"红色圆圈点开有时是科技有时是散文"——错位感打破预测惯性'))
story.append(bullet('暗色模式专门设计一套色系'))
story.append(bullet('色盲用户不受影响（颜色不承载语义）'))

story.append(add_heading('4.3 圆圈微动效（产品语言，非装饰）', h2_style, level=1))
story.append(bullet('轻微浮动（气泡感）'))
story.append(bullet('悬停时轻微放大 + 柔光'))
story.append(bullet('被fork瞬间涟漪扩散（视觉化"激发"发生了）'))
story.append(bullet('长时间未fork的圆圈慢慢变灰变薄（种子淡出视觉化）'))
story.append(Paragraph('<b>PRD必须写入交互细节，不能后期被当"锦上添花"砍掉。它们是产品语言的一部分。</b>', muted_style))

story.append(add_heading('4.4 UI用词规范', h2_style, level=1))
story.append(make_table([
    ['原词', '改为', '理由'],
    ['收藏', '收集', '弱化占有感，更符合开源精神；像森林捡拾落叶'],
    ['激发点', '一点', '双关：一个点子+一点儿灵感；轻盈感强；呼应App名'],
], col_ratios=[0.20, 0.20, 0.60]))

story.append(add_heading('4.5 工程体验坑', h2_style, level=1))
story.append(bullet('触控目标最小60pt，重叠自动避让'))
story.append(bullet('无限滚动：伪随机 + 滚动延展算法'))

story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 5: Data Structure
# ═══════════════════════════════════════════
story.append(add_heading('五、数据结构', h1_style, level=0))

story.append(add_heading('5.1 点子 Idea', h2_style, level=1))
story.append(Paragraph('<b>已砍掉字段：</b>~~type~~（避免分类思维）、~~tags[]~~（避免分类焦虑）', muted_style))
data_fields = [
    ['字段', '类型', '说明'],
    ['id', 'UUID', '唯一标识'],
    ['content', 'TEXT', '点子文本，最多300字'],
    ['source', 'ENUM', 'ugc / pgc / today_spark / fork / collide / evolve'],
    ['author_id', 'UUID', '作者用户ID'],
    ['color_hex', 'VARCHAR(7)', '从12-16色池真随机分配，与内容解耦'],
    ['border_style', 'ENUM', 'none / gold-thin — 区分自己/收集'],
    ['parent_ids[]', 'UUID[]', 'fork关系，可有多个父（碰撞=2个父）'],
    ['children_ids[]', 'UUID[]', '被fork的子点子列表'],
    ['heat', 'INT', '= fork_count，唯一热度指标'],
    ['status', 'ENUM', 'active / fading / faded — 自然淡出状态'],
    ['last_fork_at', 'TIMESTAMP', '用于种子淡出计算'],
    ['forkable', 'BOOL', '默认true，可设false拒绝衍生'],
    ['ai_assisted', 'BOOL', '是否AI辅助生成（碰撞/演化产物）'],
    ['evolved_from', 'JSON', '演化链：角度+父节点ID'],
    ['created_at', 'TIMESTAMP', '创建时间'],
]
story.append(make_table(data_fields, col_ratios=[0.22, 0.18, 0.60]))

story.append(add_heading('5.2 自然淡出规则', h2_style, level=1))
story.append(make_table([
    ['阶段', '触发条件', '视觉效果', '数据状态'],
    ['Active', '正常状态', '正常大小和颜色', '在仓库中显示'],
    ['Fading', '7天未触碰', '慢慢变小变淡', '仍在仓库中'],
    ['移出仓库', '7天+7天=14天后', '从仓库消失', '被fork过则永久存在于系统（谱系图）；未被fork则可删除'],
], col_ratios=[0.15, 0.25, 0.25, 0.35]))

story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 6: Core Mechanisms
# ═══════════════════════════════════════════
story.append(add_heading('六、核心机制', h1_style, level=0))

story.append(add_heading('6.1 Fork与谱系图', h2_style, level=1))
story.append(Paragraph('<b>Fork流程：</b>用户B看到A的点子 - 点"Fork这个点子" - 联想引导 - 写下变体 - 新点子入仓库（金边）+ 自动标注forked from A + 通知A。', body_style))
story.append(Paragraph('<b>谱系图：</b>初期只做2层（父+子），后期做完整树。每个点子详情页下方有家族树：祖先-它-后代。', body_style))

story.append(add_heading('6.2 碰撞（AI实现）', h2_style, level=1))
story.append(Paragraph('<b>交互流程：</b>', body_style))
story.append(Paragraph('仓库点击圆圈A - 弹出演化菜单 - 选"碰撞" - 选择碰撞对象圆圈B - AI生成3个结合方案 - 用户选一个（可编辑） - 新点子入仓库（金边，parent_ids=[A,B]）', code_style))
story.append(Paragraph('<b>AI提示词模板：</b>', body_style))
story.append(Paragraph('你是创意碰撞引擎。下面有两个点子，请生成3个把它们结合起来的新点子方案。\n点子A：{content_a}\n点子B：{content_b}\n要求：每个方案不超过300字，不是简单拼接而是找深层联结点，3个方案角度不同（实用型/跨界型/反常规型）。', code_style))

story.append(add_heading('6.3 演化SAMPER（AI实现）', h2_style, level=1))
story.append(Paragraph('<b>交互流程：</b>', body_style))
story.append(Paragraph('仓库点击圆圈 - 弹出演化菜单 - 选"演化" - 选择SAMPER角度 - AI生成3个变体 - 用户选一个（可编辑） - 新点子入仓库（金边，evolved_from={角度, 父ID}）', code_style))
story.append(Paragraph('<b>AI提示词模板：</b>', body_style))
story.append(Paragraph('你是创意演化引擎。下面是一个点子和一个SAMPER角度，请生成3个变体。\n点子：{content}\n角度：{angle}（{angle_desc}）\n要求：每个变体不超过300字，保留核心洞察但在指定角度有创新，3个变体不同程度远离原点子（近/中/远）。', code_style))

story.append(add_heading('6.4 今日一点', h2_style, level=1))
story.append(bullet('每日一题：随机词/类比题/约束题/反向提问'))
story.append(bullet('3分钟倒计时，倒计时结束自动保存草稿'))
story.append(bullet('草稿保留到当日23:59，过期清空'))
story.append(bullet('错过当日不能补做'))
story.append(bullet('第一次保存草稿时弹窗："草稿已保存。保留到今晚23:59，明天就清空啦，记得回来完成！"'))

story.append(add_heading('6.5 内容审核', h2_style, level=1))
story.append(make_table([
    ['环节', '方式', '说明'],
    ['AI审核', 'DeepSeek + 违禁词库', '秒级审核，先发后审不阻塞UGC'],
    ['违规撤回', '自动', 'AI判定违规立即撤回'],
    ['用户举报', '人工入口', '用户举报后进入人工二审队列'],
    ['人工二审', '运营人员', '处理AI误判和边界案例'],
], col_ratios=[0.18, 0.27, 0.55]))

story.append(add_heading('6.6 热度算法', h2_style, level=1))
story.append(Paragraph('<b>公式：</b>圆圈大小 = f(fork数, 近期fork衰减)', body_style))
story.append(Paragraph('<b>主页圆圈构成：</b>90%随机 + 10%热门（近30天fork数Top，滚动窗口每日重算）', body_style))
story.append(Paragraph('<b>拒绝复杂算法：</b>不引入第三变量，与抖音式推荐划清界限。自然淡出机制平衡马太效应。', muted_style))

story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 7: Tech Stack
# ═══════════════════════════════════════════
story.append(add_heading('七、技术方案', h1_style, level=0))

story.append(add_heading('7.1 前端：Flutter', h2_style, level=1))
story.append(make_table([
    ['方面', '选型', '理由'],
    ['框架', 'Flutter (Dart)', '一套代码双端，MVP效率最高'],
    ['状态管理', 'Riverpod（推荐）', '类型安全、可测试、社区活跃'],
    ['圆圈渲染', 'CustomPainter', '高性能Canvas绘制，支持复杂动画'],
    ['动效', 'Animation Framework', '浮动/涟漪/淡出/步行漫游动效'],
    ['震动反馈', 'HapticFeedback class', '全平台支持，iOS/Android均可'],
    ['网络', 'dio + retrofit', '类型安全的HTTP客户端'],
    ['本地存储', 'Hive / SharedPreferences', '轻量缓存，离线草稿'],
], col_ratios=[0.18, 0.27, 0.55]))

story.append(add_heading('7.2 后端：FastAPI + PostgreSQL', h2_style, level=1))
story.append(make_table([
    ['组件', '选型', '用途'],
    ['Web框架', 'FastAPI', '异步API，自动文档，高性能'],
    ['数据库', 'PostgreSQL', '用户/点子/Fork关系，递归CTE查询谱系图'],
    ['缓存', 'Redis', '会话/热门点子缓存/限流'],
    ['AI', 'DeepSeek (deepseek-chat)', '碰撞/演化/审核，temperature=0.9'],
    ['图关系', 'PostgreSQL递归CTE', 'MVP够用，后期可迁移Neo4j'],
], col_ratios=[0.15, 0.25, 0.60]))

story.append(add_heading('7.3 API规格（核心）', h2_style, level=1))
story.append(Paragraph('<b>点子CRUD：</b>', body_style))
story.append(Paragraph('POST /api/ideas  - 发布点子\nGET /api/ideas/{id}  - 点子详情\nGET /api/ideas/explore  - 主页探索（90%随机+10%热门）\nGET /api/ideas/vault  - 我的仓库', code_style))
story.append(Paragraph('<b>Fork与演化：</b>', body_style))
story.append(Paragraph('POST /api/ideas/{id}/fork  - Fork联想\nPOST /api/ideas/collide  - 碰撞（传入两个idea_id）\nPOST /api/ideas/{id}/evolve  - 演化（传入SAMPER角度）', code_style))
story.append(Paragraph('<b>今日一点：</b>', body_style))
story.append(Paragraph('GET /api/spark/today  - 今日题目\nPOST /api/spark/submit  - 提交\nPOST /api/spark/draft  - 保存草稿', code_style))
story.append(Paragraph('<b>谱系图：</b>', body_style))
story.append(Paragraph('GET /api/ideas/{id}/lineage  - 谱系（父+子，2层）', code_style))

story.append(add_heading('7.4 成本估算', h2_style, level=1))
story.append(make_table([
    ['项目', '单次成本', '日用量（估）', '月成本（估）'],
    ['碰撞AI调用', '~0.004元', '100次', '~12元'],
    ['演化AI调用', '~0.004元', '100次', '~12元'],
    ['审核AI调用', '~0.001元', '1000次', '~30元'],
    ['DeepSeek总成本', '-', '-', '~54元/月'],
    ['服务器', '-', '-', '~200元/月'],
    ['合计', '-', '-', '~254元/月'],
], col_ratios=[0.25, 0.20, 0.20, 0.35]))
story.append(Paragraph('MVP阶段成本极低，后期根据实际用量调整。', muted_style))

story.append(PageBreak())

# ═══════════════════════════════════════════
# Chapter 8: Development Plan
# ═══════════════════════════════════════════
story.append(add_heading('八、开发计划', h1_style, level=0))

story.append(add_heading('8.1 MVP范围', h2_style, level=1))
story.append(Paragraph('先开发不上线，拿到社群测试后再做决定。MVP包含：', body_style))
story.append(bullet('9个核心页面（主页/仓库/今日一点/详情页/个人主页/发布/Fork引导/通知/设置）'))
story.append(bullet('碰撞 + 演化（SAMPER 6角度）AI辅助'))
story.append(bullet('Fork + 谱系图（2层）'))
story.append(bullet('今日一点（每日一题 + 倒计时 + 草稿）'))
story.append(bullet('自然淡出机制'))
story.append(bullet('AI审核 + 违禁词库'))
story.append(bullet('圆圈随机分布 + 12-16色池 + 微动效'))
story.append(bullet('演化菜单步行体验 + 震动反馈'))

story.append(add_heading('8.2 Phase划分', h2_style, level=1))
story.append(make_table([
    ['Phase', '内容', '周期（估）'],
    ['Phase 1', 'Flutter项目搭建 + 后端API骨架 + 点子CRUD + 主页圆圈渲染', '1-2周'],
    ['Phase 2', 'Fork流程 + 谱系图 + 仓库 + 个人主页', '1-2周'],
    ['Phase 3', '碰撞 + 演化AI + 今日一点 + 审核机制', '1-2周'],
    ['Phase 4', '动效打磨 + 震动反馈 + 暗色模式 + 测试', '1周'],
    ['合计', 'MVP交付', '4-7周'],
], col_ratios=[0.12, 0.63, 0.25]))

story.append(add_heading('8.3 冷启动内容池', h2_style, level=1))
story.append(bullet('PGC 500-1000条精选点子（冷启动期PGC反超到70%+）'))
story.append(bullet('来源候选：Hacker News高赞 / Kickstarter经典 / 创新案例库 / 创造力文献案例'))
story.append(bullet('今日一点题库：随机词/类比题/约束题/反向提问，需单独设计一套'))

story.append(add_heading('8.4 砍掉的功能（记录）', h2_style, level=1))
story.append(make_table([
    ['功能', '砍掉理由'],
    ['type（预设分类）', '避免分类思维，强化发散定位'],
    ['tag（自由标签）', '避免分类焦虑，与type同性质'],
    ['搜索', '强制随机激发，不做信息检索；谱系图导航不算搜索'],
    ['连线', '笔记软件功能，与无序哲学矛盾；碰撞已吸收其价值'],
    ['种子', '与自然淡出重叠，简化为单一机制'],
    ['SCAMPER的C（Combine）', '已由碰撞功能承担，避免重叠'],
], col_ratios=[0.25, 0.75]))

story.append(add_heading('8.5 待后续迭代', h2_style, level=1))
story.append(bullet('完整谱系树（超过2层）'))
story.append(bullet('碰撞/演化每日次数限制（成本模型）'))
story.append(bullet('暗色模式色系优化'))
story.append(bullet('私密点子选项（用户反馈驱动）'))
story.append(bullet('多时区支持'))
story.append(bullet('多模态（图片/声音刺激）'))

# ─── Build ───
doc = TocDocTemplate(
    '/home/z/my-project/idea-app/点子App_PRD_V1.0_body.pdf',
    pagesize=A4,
    leftMargin=left_m, rightMargin=right_m,
    topMargin=0.9*inch, bottomMargin=0.9*inch,
    title='点子 App PRD V1.0',
    author='Sam',
)
doc.multiBuild(story)
print('Body PDF generated: 点子App_PRD_V1.0_body.pdf')
