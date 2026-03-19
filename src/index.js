#!/usr/bin/env node
const dataset = [
  {
    "name": "@fjordsketch",
    "heat": 0.87
  },
  {
    "name": "@auroraaudio",
    "heat": 0.92
  },
  {
    "name": "@northernknots",
    "heat": 0.74
  }
];

function highlightEntries() {
  return dataset
    .filter(entry => entry['heat'] >= 0.8)
    .map(entry => ({ name: entry.name, score: entry['heat'] }));
}

console.log('
Creator Spark Registry');
console.log('Micro-CRM for tracking which creators to cheer on.');
console.log('
Top signals:');
highlightEntries().forEach((entry, idx) => {
  const rank = String(idx + 1).padStart(2, ' ');
  console.log(' ' + rank + '. ' + entry.name + ' (' + entry.score + ')');
});
