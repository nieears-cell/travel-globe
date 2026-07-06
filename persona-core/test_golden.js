// node test_golden.js —— 跑黄金用例,验证判定引擎
var fs = require('fs');
var path = require('path');
var rules = require('./personalityRules.js');
var cities = JSON.parse(fs.readFileSync(path.join(__dirname, 'cities.json'), 'utf8')).cities;
var golden = JSON.parse(fs.readFileSync(path.join(__dirname, 'goldenCases.json'), 'utf8')).cases;

var byName = {};
cities.forEach(function (c) { byName[c.name] = c; });

var pass = 0, fail = 0;
golden.forEach(function (g, i) {
  var sel = g.cities.map(function (n) { if (!byName[n]) throw new Error('城市未在 cities.json: ' + n); return byName[n]; });
  var r = rules.judge(sel, g.answers);
  var ok = r.type === g.expect;
  if (g.expectNeedMore != null) ok = ok && (r.needMoreCities === g.expectNeedMore);
  if (ok) { pass++; }
  else {
    fail++;
    var sorted = Object.keys(r.scores).sort(function (a, b) { return r.scores[b] - r.scores[a]; })
      .slice(0, 3).map(function (t) { return t + '=' + r.scores[t].toFixed(2); }).join(', ');
    console.log('✗ #' + (i + 1) + ' ' + g.desc + '\n   预期 ' + g.expect + ' 实得 ' + r.type + '  | top3: ' + sorted);
  }
});
console.log('\n结果: ' + pass + ' 过 / ' + fail + ' 败  (共 ' + golden.length + ')');
process.exit(fail ? 1 : 0);
