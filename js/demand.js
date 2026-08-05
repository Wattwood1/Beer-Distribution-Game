// Customer demand generators. Mirrors env/demand.py.

export function stepDemand(week) {
  return week <= 4 ? 4 : 8;
}

export function zeroDemand(_week) {
  return 0;
}
