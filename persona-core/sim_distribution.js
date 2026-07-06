// node sim_distribution.js —— 蒙特卡洛:随机选城+随机答题,看 8 型分布会不会扎堆
var fs = require('fs'), path = require('path');
var rules = require('./personalityRules.js');
var cities = JSON.parse(fs.readFileSync(path.join(__dirname, 'cities.json'), 'utf8')).cities;
var OPTS = ['A', 'B', 'C', 'D'];
var N = 20000;
// 伪随机(可复现,不依赖 Math.random 的种子问题)
var seed = 12345;
function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }
function pick(arr) { return arr[Math.floor(rnd() * arr.length)]; }

var tally = {}; rules.TYPES.forEach(function (t) { tally[t] = 0; });
for (var i = 0; i < N; i++) {
  var k = 3 + Math.floor(rnd() * 6);            // 3~8 城
  var pool = cities.slice(), sel = [];
  for (var j = 0; j < k && pool.length; j++) { sel.push(pool.splice(Math.floor(rnd() * pool.length), 1)[0]); }
  var r = rules.judge(sel, { q1: pick(OPTS), q2: pick(OPTS), q3: pick(OPTS) });
  tally[r.type]++;
}
console.log('随机选城+随机答题 ' + N + ' 次的人格分布:');
rules.TYPES.map(function (t) { return [t, tally[t]]; })
  .sort(function (a, b) { return b[1] - a[1]; })
  .forEach(function (x) { console.log('  ' + (x[1] / N * 100).toFixed(1).padStart(5) + '%  ' + x[0]); });
var hit = rules.TYPES.filter(function (t) { return tally[t] / N >= 0.05; }).length;
console.log('占比≥5% 的型数:' + hit + ' / 8');
// CI 门:固定种子下每一型都必须 ≥5%(防止改判定规则后分布悄悄扎堆)
if (hit < rules.TYPES.length) {
  console.error('FAIL: 有人格型占比 < 5%,分布扎堆,判定规则需要回炉');
  process.exit(1);
}
console.log('PASS: 8/8 型占比均 ≥5%');
