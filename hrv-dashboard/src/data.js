// Simulated 30-day HRV dataset (realistic clinical ranges)
export function generateHRVData() {
  const days = [];
  const now = new Date();
  let baseHRV = 58, baseSleep = 7.2, baseStrain = 12;

  for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });

    const event = i === 18 ? -14 : i === 12 ? -10 : i === 5 ? 8 : 0;
    const hrv = Math.max(30, Math.min(95, baseHRV + event + (Math.random() - 0.5) * 8));
    baseHRV += (Math.random() - 0.48) * 1.5;

    const sleep = Math.max(4.5, Math.min(9.5, baseSleep + (Math.random() - 0.5) * 1.2));
    baseSleep += (Math.random() - 0.5) * 0.3;

    const strain = Math.max(4, Math.min(21, baseStrain + (Math.random() - 0.5) * 4));
    baseStrain += (Math.random() - 0.5) * 0.5;

    const rmssd = Math.round(hrv);
    const sdnn = Math.round(rmssd * 1.3 + (Math.random() - 0.5) * 6);
    const recovery = Math.round(Math.min(100, Math.max(20,
      (rmssd / 95) * 50 + (sleep / 9.5) * 30 + (1 - strain / 21) * 20
    )));

    days.push({
      label, rmssd, sdnn,
      sleep: parseFloat(sleep.toFixed(1)),
      strain: parseFloat(strain.toFixed(1)),
      recovery,
      date: d.toISOString().split("T")[0]
    });
  }
  return days;
}

export function recoveryColor(v) {
  if (v >= 67) return "#1D9E75";
  if (v >= 34) return "#BA7517";
  return "#D85A30";
}

export function recoveryLabel(v) {
  if (v >= 67) return "Green";
  if (v >= 34) return "Yellow";
  return "Red";
}

export function avg(arr, key) {
  return arr.reduce((s, d) => s + d[key], 0) / arr.length;
}
