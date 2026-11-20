import { fromIsoDate, isOverdue, toIsoDate } from './notify';

describe('date helpers', () => {
  it('formats dates as local YYYY-MM-DD', () => {
    expect(toIsoDate(new Date(2030, 0, 5))).toBe('2030-01-05');
    expect(toIsoDate(null)).toBeNull();
  });

  it('parses ISO dates in local time', () => {
    const date = fromIsoDate('2030-12-31');
    expect(date?.getFullYear()).toBe(2030);
    expect(date?.getMonth()).toBe(11);
    expect(date?.getDate()).toBe(31);
  });

  it('flags unfinished tasks past their due date', () => {
    expect(isOverdue('2000-01-01', 'todo')).toBe(true);
    expect(isOverdue('2000-01-01', 'done')).toBe(false);
    expect(isOverdue('2999-01-01', 'todo')).toBe(false);
    expect(isOverdue(null, 'todo')).toBe(false);
  });
});
