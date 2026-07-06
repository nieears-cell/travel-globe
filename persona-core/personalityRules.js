/*
 * 旅行人格判定引擎(确定性,无 AI)
 * judge(cities, answers) -> { type, scores, benming, benmingFromUser, needMoreCities, cityCount }
 *  - cities: 用户勾选的城市对象数组(取自 cities.json)
 *  - answers: { q1, q2, q3 },每项 'A'|'B'|'C'|'D'
 * 评分原则(经 Codex 修正):
 *  - 城市信号用"占比"(命中标签的城市数 / 勾选总数),使选 3 城与选 12 城口径一致
 *  - 题目作"强权重"修正(行为型人格靠题目压过城市标签)
 *  - 并列时"稀缺/有记忆点"的型优先,防止人人都落到松弛感/出片型(分布保护)
 *  - 兜底:勾选 < 3 城仍出结果(题目主导)并提示;本命城市优先取用户勾过的城,否则交由文案层给"下一站"
 */
(function (global) {
  var TYPES = ['松弛感本人', '特种兵旅人', 'citywalk 漫游家', '反向旅游选手', '老城散步派', '为了一口吃的', '出片型人格', '周末治愈系'];
  // 并列优先级:稀缺/独特在前,常见默认型(松弛/出片)在后
  var PRIORITY = ['反向旅游选手', '为了一口吃的', '老城散步派', '特种兵旅人', '周末治愈系', 'citywalk 漫游家', '出片型人格', '松弛感本人'];

  function judge(cities, answers) {
    cities = cities || [];
    answers = answers || {};
    var n = cities.length;
    function ratio(pred) { return n ? cities.filter(pred).length / n : 0; }
    var tagRatio = function (tag) { return ratio(function (c) { return (c.tags || []).indexOf(tag) >= 0; }); };
    var heatRatio = function (h) { return ratio(function (c) { return c.heat === h; }); };
    var costRatio = function (t) { return ratio(function (c) { return c.travelCost === t; }); };
    var regionSpread = (function () { var s = {}; cities.forEach(function (c) { if (c.region) s[c.region] = 1; }); return Object.keys(s).length; })();
    var q = function (key, val) { return answers[key] === val ? 1 : 0; };
    var QW = 1.1; // 题目强权重

    var s = {};
    s['松弛感本人']     = 1.0 * tagRatio('度假松弛') + 0.8 * tagRatio('海岛海滨') + QW * q('q1', 'C') + QW * q('q3', 'D');
    s['特种兵旅人']     = 0.5 * Math.min(1, n / 6) + 0.5 * Math.min(1, (regionSpread - 1) / 3) + 1.3 * q('q1', 'A');
    s['citywalk 漫游家'] = 1.0 * tagRatio('大都市') + QW * q('q2', 'D') + 0.5 * q('q1', 'B');
    s['反向旅游选手']   = 1.0 * tagRatio('小众秘境') + 0.8 * heatRatio('小众') + QW * q('q2', 'C') + QW * q('q3', 'A');
    s['老城散步派']     = 1.1 * tagRatio('古城人文') + 0.6 * q('q1', 'B') + QW * q('q3', 'C');
    s['为了一口吃的']   = 1.2 * tagRatio('美食之都') + QW * q('q2', 'B');
    s['出片型人格']     = 1.0 * tagRatio('出片打卡') + 0.5 * heatRatio('热门') + QW * q('q2', 'A');
    s['周末治愈系']     = 0.9 * costRatio('周末友好') + 0.5 * tagRatio('自然山水') + 0.4 * tagRatio('度假松弛') + QW * q('q3', 'B') + (n > 0 && n <= 3 ? 0.25 : 0);

    // 取最高;按 PRIORITY 顺序遍历,实现"并列时稀缺型优先"
    var best = null, bestScore = -1;
    PRIORITY.forEach(function (t) { if (s[t] > bestScore + 1e-9) { bestScore = s[t]; best = t; } });

    // 本命城市:优先取用户勾过、且 bestTypes 含结果型的城;否则取第一座;都没有则 null(交文案层给"下一站")
    var benming = null, benmingFromUser = false;
    var matched = cities.filter(function (c) { return (c.bestTypes || []).indexOf(best) >= 0; });
    if (matched.length) { benming = matched[0].name; benmingFromUser = true; }
    else if (n) { benming = cities[0].name; benmingFromUser = true; }

    return {
      type: best,
      scores: s,
      benming: benming,
      benmingFromUser: benmingFromUser,
      needMoreCities: n > 0 && n < 3,
      cityCount: n
    };
  }

  var api = { judge: judge, TYPES: TYPES, PRIORITY: PRIORITY };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.PersonaRules = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
