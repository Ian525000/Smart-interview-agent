const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');

// Small DOM adapter for testing request/state transitions without real APIs or a microphone.
class Element {
  constructor(id = '', classes = '') {
    this.id = id;
    this.classes = new Set(classes.split(/\s+/).filter(Boolean));
    this.classList = {
      add: (...names) => names.forEach(name => this.classes.add(name)),
      remove: (...names) => names.forEach(name => this.classes.delete(name)),
      contains: name => this.classes.has(name),
      toggle: (name, force) => {
        const selected = force ?? !this.classes.has(name);
        selected ? this.classes.add(name) : this.classes.delete(name);
        return selected;
      },
    };
    this.attributes = new Map();
    this.listeners = new Map();
    this.children = [];
    this.style = {};
    this.dataset = {};
    this.files = [];
    this.value = '';
    this.disabled = false;
    this.hidden = false;
    this.checked = false;
    this._text = '';
  }
  get className() { return [...this.classes].join(' '); }
  set className(value) { this.classes = new Set(value.split(/\s+/).filter(Boolean)); }
  get textContent() { return this._text; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get innerHTML() { return this._html || ''; }
  set innerHTML(value) { this._html = value; this.children = []; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  addEventListener(event, handler) { this.listeners.set(event, handler); }
  appendChild(child) { this.children.push(child); }
  querySelector() { return this.em || (this.em = new Element()); }
  focus() {}
  scrollIntoView(options) { this.lastScroll = options; }
  click() { return this.listeners.get('click')?.({ currentTarget: this }); }
}

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const session = () => ({
  session_id: 'frontend-test', phase: 'preview',
  jd_profile: { title: '产品经理', company: '示例团队' },
  resume_profile: { name: '示例候选人' }, follow_up_targets: ['q2'],
  questions: Array.from({ length: 10 }, (_, index) => ({
    id: `q${index + 1}`, type: 'project', text: `第 ${index + 1} 道测试问题`, suggested_minutes: 2,
  })),
  scores: [],
});

function harness(customFetch) {
  const elements = new Map();
  for (const tag of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    elements.set(tag[1], new Element(tag[1], tag[0].match(/\bclass="([^"]+)"/)?.[1] || ''));
  }
  const body = new Element();
  body.dataset.step = 'step-upload';
  const container = new Element('', 'container');
  const uploadCard = new Element('', 'upload-card');
  const workflow = Array.from({ length: 5 }, () => new Element('', 'workflow-step'));
  const events = new Map();
  const intervals = new Map();
  const state = { now: 0, questionFields: [] };
  const allChildren = root => root.children.flatMap(child => [child, ...allChildren(child)]);
  const document = {
    body,
    getElementById: id => elements.get(id),
    createElement: () => new Element(),
    addEventListener: (event, handler) => events.set(event, handler),
    querySelector: selector => selector === '.container' ? container
      : selector === '.upload-card' ? uploadCard
      : [...elements.values()].find(el => el.classes.has('step') && el.classes.has('active')),
    querySelectorAll: selector => selector === '.workflow-step' ? workflow
      : selector === '#questions-list textarea' ? state.questionFields
      : allChildren(elements.get('session-list')).filter(el => el.classes.has('session-check')
        && (!selector.includes(':checked') || el.checked)),
  };
  class Clock extends Date { static now() { return state.now; } }
  const context = vm.createContext({
    document, Date: Clock, TypeError, FormData, setTimeout, clearTimeout,
    setInterval: callback => { const id = Symbol(); intervals.set(id, callback); return id; },
    clearInterval: id => intervals.delete(id),
    window: { scrollTo() {}, matchMedia: () => ({ matches: false }) },
    fetch: async (url, options) => {
      if (customFetch) {
        const result = await customFetch(url, options);
        if (result !== undefined) return result;
      }
      if (url === '/api/templates') return response({ templates: [] });
      if (url === '/api/sessions') return response({ sessions: [] });
      if (url === '/api/config') return response({ max_record_seconds: 120 });
      throw new Error(`Unexpected request: ${url}`);
    },
  });
  vm.runInContext(source, context);
  return {
    elements, context, state, intervals,
    run: expression => vm.runInContext(expression, context),
    initialize: () => events.get('DOMContentLoaded')(),
  };
}

test('API initialization failure leaves real controls bound and provides a retry path', async () => {
  const h = harness(url => {
    if (url !== '/api/config') throw new TypeError('offline');
  });
  await h.initialize();
  assert.ok(h.elements.get('btn-create').listeners.has('click'));
  assert.ok(h.elements.get('btn-refresh-sessions').listeners.has('click'));
  assert.match(h.elements.get('session-list').innerHTML, /刷新/);
  await h.elements.get('btn-create').click();
  assert.match(h.elements.get('upload-status').textContent, /两个文件/);
});

test('generation prevents duplicate submissions and still opens questions if history refresh fails', async () => {
  let resolveCreation;
  let creations = 0;
  const h = harness(url => {
    if (url === '/api/sessions/text') {
      creations++;
      return new Promise(resolve => { resolveCreation = resolve; });
    }
    if (url === '/api/sessions') throw new TypeError('offline');
  });
  h.elements.get('jd-text').value = '目标岗位';
  h.elements.get('resume-text').value = '示例经历';
  h.elements.get('btn-create').textContent = '生成面试题';
  const first = h.run('createSession()');
  assert.equal(h.elements.get('btn-create').disabled, true);
  await h.run('createSession()');
  assert.equal(creations, 1);
  resolveCreation(response(session()));
  await first;
  assert.equal(h.run('document.body.dataset.step'), 'step-preview');
  assert.equal(h.elements.get('questions-list').children.length, 10);
  assert.equal(h.elements.get('btn-create').disabled, false);
  assert.equal(h.elements.get('btn-create').textContent, '生成面试题');
});

test('edited questions survive mode selection and returning to the editor', async () => {
  const record = session();
  const h = harness((url, options) => {
    if (options?.method === 'PUT') return response({ ...record, questions: JSON.parse(options.body).questions });
  });
  await h.initialize();
  h.context.record = record;
  h.run('currentSession = record; sessionId = record.session_id');
  h.state.questionFields = record.questions.map(question => ({ value: question.text }));
  h.state.questionFields[0].value = '修改后的真实问题';
  await h.run('goToModeStep()');
  assert.equal(h.run('currentSession.questions[0].text'), '修改后的真实问题');
  await h.elements.get('btn-mode-voice').click();
  assert.equal(h.elements.get('btn-mode-voice').getAttribute('aria-pressed'), 'true');
  assert.equal(h.elements.get('btn-begin-interview').disabled, false);
  await h.elements.get('btn-mode-back').click();
  assert.equal(h.run('document.body.dataset.step'), 'step-preview');
  assert.equal(h.state.questionFields[0].value, '修改后的真实问题');
});

test('report failure hides downloads and makes retry available', async () => {
  const h = harness(url => url.includes('/frontend-test') ? response({ detail: '报告读取失败' }, 503) : undefined);
  h.run('sessionId = "frontend-test"');
  await h.run('showReport(null)');
  assert.match(h.elements.get('report-status').textContent, /报告读取失败/);
  assert.equal(h.elements.get('report-downloads').hidden, true);
  assert.equal(h.elements.get('btn-report-retry').classList.contains('hidden'), false);
  assert.equal(h.elements.get('report-summary').getAttribute('aria-busy'), null);
});

test('real report data retains ten feedback items and report/transcript download URLs', async () => {
  const record = session();
  record.phase = 'completed';
  record.summary = { average_score: 4, strengths: ['结构清楚'], risks: [], next_steps: '补充验证结果' };
  record.scores = record.questions.map(question => ({
    question_id: question.id, total_score: 4, dimensions: [], feedback: '提供了具体行动',
    evidence_quotes: ['先进行用户访谈'], high_score_framework: '先描述目标，再解释行动与结果',
  }));
  const h = harness(url => url.includes('/frontend-test') ? response(record) : undefined);
  await h.initialize();
  h.run('sessionId = "frontend-test"');
  await h.run('showReport(null)');
  assert.equal(h.elements.get('scores-list').children.length, 10);
  assert.match(h.elements.get('scores-list').children[0].innerHTML, /高分作答框架/);
  assert.equal(h.elements.get('report-downloads').hidden, false);
  assert.equal(h.elements.get('btn-download-pdf').href, '/api/sessions/frontend-test/report?format=pdf');
  assert.equal(h.elements.get('btn-download-qa-md').href, '/api/sessions/frontend-test/transcript?format=md');
  await h.elements.get('btn-report-back').click();
  assert.equal(h.run('document.body.dataset.step'), 'step-preview');
});

test('continuous transcript keeps earlier sentences and the two-minute limit stops without discarding text', async () => {
  const h = harness();
  h.run('savedAnswerText = "第一句话。"; sessionFinalTranscript = "第二句话。"; commitSessionTranscript(); sessionInterimTranscript = "第三句话。"; isRecording = true; updateAnswerDisplay(); startRecordingTimer()');
  assert.equal(h.elements.get('user-transcript').textContent, '第一句话。第二句话。第三句话。');
  h.state.now = 95000;
  [...h.intervals.values()][0]();
  assert.equal(h.elements.get('recording-timer').classList.contains('warning'), true);
  h.state.now = 115000;
  [...h.intervals.values()][0]();
  assert.equal(h.elements.get('recording-timer').classList.contains('danger'), true);
  h.state.now = 120000;
  [...h.intervals.values()][0]();
  assert.equal(h.run('isRecording'), false);
  assert.equal(h.elements.get('recording-timer').classList.contains('hidden'), true);
  assert.equal(h.elements.get('user-transcript').textContent, '第一句话。第二句话。第三句话。');
  assert.match(h.elements.get('interview-status').textContent, /内容已保留/);
});

test('browser speech fallback can replay the current question without keeping previous audio', async () => {
  const h = harness();
  h.context.record = session();
  h.run('currentSession = record; answerMode = "text"; lastAudioBase64 = "previous-question-audio"; typewriterEffect = async () => {}; playAgentSpeech = async () => {}');
  await h.run('handleWsMessage({ agent_text: "第 1 题：介绍你的项目。", question_index: 0, total: 10, tts_fallback: true })');
  assert.equal(h.run('lastAudioBase64'), null);
  assert.equal(h.elements.get('btn-replay').disabled, false);
  assert.equal(h.elements.get('speech-state').textContent, '等待回答');
});
