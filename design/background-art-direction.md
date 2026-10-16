# 智能面试 Agent · 背景视觉方案

已选择并应用「真实办公 · 蓝调」。正式网页地址：http://localhost:8001/ 。首页采用会议室与城市夜景的完整背景；正式面试保留深蓝办公氛围，以白色问题与回答区域保障长文本阅读。题目预览、回答方式与报告页面沿用同一背景和品牌色。

主题样式：`static/office-theme.css`。前端通过 `body[data-step]` 选择不同阶段的背景强度，仍使用现有上传、题目编辑、语音/文字作答及报告接口。

正式功能地址：http://localhost:8001/

视觉对比地址：http://localhost:8001/static/design-gallery.html

原 `http://localhost:8001/static/background-preview.html` 已改为正式应用的兼容入口，自动转到首页。原有功能使用实际接口；视觉对比页面另行保留。正式页面提供返回编辑、历史刷新、生成中状态和报告失败重试。

## 三个方向

| 方向 | 与项目的关联 | 建议用法 |
| --- | --- | --- |
| 产品思维 · 暖白（推荐） | 产品原型、用户旅程、数据洞察、语音波形；直接呈现产品经理工作的内容 | 准备页清晰展示背景，正式面试用浅色遮罩和白色阅读区域 |
| 真实办公 · 蓝调 | 现代互联网团队的会议和面试空间，更有临场感 | 准备页深色横幅，正式面试保留空间氛围与白色对话区域 |
| 智能对话 · 深蓝 | 声音到结构化思考，强调语音与 AI Agent 的产品特点 | 准备页深蓝主视觉，正式面试弱化背景光效 |

## 五页应用方式

- 上传 JD / 简历：背景图作为宽幅首页主视觉，正文左侧留白、图像右侧聚焦，上传区域与历史会话位于下方。
- 预览编辑题目：使用同图的局部横幅，题目列表保持实底，完整保留长文本编辑空间。
- 选择回答方式：简洁的主题横幅配合两张明显可选的模式卡片，选项作用于整场面试。
- 正式面试：背景存在于页头与边缘，问题、长回答和录音操作放在高对比实底区域，保留题号、追问、实时转写和 2 分钟倒计时。
- 评估报告：收敛为较矮的主题图横幅，评分摘要与逐题反馈保持白色实底和可展开布局。
- 手机：优先保留主体图像，标题单独留出空间；题目、回答与录音操作纵向排列，避免把桌面全图缩小塞入手机屏幕。

## 素材

生成方式：内置 imagegen 工具，三个独立提示词。生成文件复制到本项目 static/assets/backgrounds，原始图保留。

- `static/assets/backgrounds/product-workbench-v1.png`
- `static/assets/backgrounds/office-blue-hour-v1.png`
- `static/assets/backgrounds/ai-dialogue-navy-v1.png`

所有图片均无真实公司标志、人物或嵌入文字。预览中的问答为合成示例，不读取候选人资料，也不创建面试记录。

## 最终生成提示词

### 产品思维 · 暖白

```text
Use case: stylized-concept. Asset type: wide 16:9 hero background illustration for a professional Chinese AI mock interview web app for product manager roles at major internet companies. Primary request: beautiful high-end editorial 3D illustration of a product-thinking workbench, distinctive and tangible, with warm off-white ceramic paper-like cards and frosted glass panels representing user journeys, wireframes, data insight and a calm audio waveform. Arrange a small sculptural composition on the right half: layered blank UX wireframe cards with minimal cobalt blue rounded rectangles, a small clear-glass bar-chart sculpture, one tactile soft coral sphere and folded paper surfaces connected by a thin elegant blue path. No literal robot, no generic AI brain. Strong material realism, detailed soft contact shadows, translucent glass edges, subtle paper fiber and ceramic texture, refined rather than toy-like. Warm ivory studio backdrop with a soft blue atmospheric horizon and quiet daylight. Composition: extra-wide negative space on the left 55 percent for a dark navy page heading; right half is visibly richer and has an aesthetically balanced focal point; lower edge clean so a white upload panel can overlap without visual conflict. Color palette: warm ivory, ink navy, cobalt blue, tiny coral accent. Premium modern internet product editorial art. Constraints: actual background image only, no website UI, no text, no numbers, no logos, no human figure, no watermark. Generate in 16:9 landscape.
```

### 真实办公 · 蓝调

```text
Use case: photorealistic-natural. Asset type: wide 16:9 hero background image for a Chinese web application that helps candidates practice interviews for product manager roles at major internet companies. Primary request: a premium, photorealistic editorial photograph of a quiet modern internet product-team interview room at blue hour. Scene: understated meeting table and two comfortable empty chairs toward the right, large glass windows with a softly defocused modern city, an elegant dark laptop and a subtle wall of product planning notes with no readable writing. Calm, thoughtful, professional, welcoming rather than intimidating. Composition: panoramic landscape, the left 55 percent remains a very simple dark navy shadowed wall / defocused space reserved for white website headline; the recognisable room, table and window are on the right 45 percent, usable for a cropped mobile hero. Materials: real wood grain, brushed metal, gentle reflections, natural lens depth. Lighting: soft warm practical light contrasting with cool cobalt exterior, restrained cinematic lighting. High-end architecture photography, natural texture, premium career education product identity. Constraints: background asset only, no website UI, no words, no letters, no company logos, no people, no watermark. Not a hospital, not a classroom. Large image in 16:9 landscape.
```

### 智能对话 · 深蓝

```text
Use case: stylized-concept. Asset type: wide 16:9 brand background for a Chinese voice-powered AI mock interview app for internet product manager candidates. Primary request: a sophisticated abstract visual representing conversation becoming structured product thinking, an elegant sculptural flowing cobalt and pale cyan glass ribbon shaped like a restrained audio waveform, transitioning into a few interlinked translucent rounded glass planes / clear blocks at the right. Deep midnight navy background with nuanced blue atmospheric light, photographic 3D quality, gorgeous transparent refractive materials, subtle grain and clean shadows. Composition: most of the sculptural form remains in the right 45 percent and lower right; the left 55 percent is visually quiet almost-solid ink navy for white Chinese website headline and concise supporting copy. A premium modern career-product identity, expressive but calm, no excessive glow. Constraints: background image asset only, no webpage layout, no text, no letters, no numbers, no logos, no faces, no humanoid robots, no circuit-board cliché, no stars, no sci-fi spaceship, no watermark. 16:9 landscape.
```
