#ifndef MERC360_KERNEL_CLOCK_CORE_H
#define MERC360_KERNEL_CLOCK_CORE_H
/* Phase6 K1A: pure original-Xbox 100ns/UTC calendar conversion.
 * No host clock, guest memory, kernel, or Xbox XDK dependencies.
 * Year range is 1601..9999 (representable FILETIME era).
 * A TIME_FIELDS value has eight signed 16-bit fields in order.
 */
#include <stdint.h>
namespace merc360_k1 {
struct TimeFields {
    int16_t year, month, day, hour, minute, second, milliseconds, weekday;
};
static inline bool leap(int y) {
    return (y % 4 == 0) && ((y % 100 != 0) || (y % 400 == 0));
}
static inline int month_length(int year, int month) {
    static const int days[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
    if (month < 1 || month > 12) return 0;
    return days[month - 1] + ((month == 2 && leap(year)) ? 1 : 0);
}
static const uint64_t TICKS_SECOND = UINT64_C(10000000);
static const uint64_t TICKS_DAY = UINT64_C(864000000000);
static inline bool to_ticks(const TimeFields& x, uint64_t* out) {
    if (!out || x.year < 1601 || x.year > 9999 ||
        x.month < 1 || x.month > 12 || x.day < 1 ||
        x.day > month_length(x.year, x.month) || x.hour < 0 || x.hour > 23 ||
        x.minute < 0 || x.minute > 59 || x.second < 0 || x.second > 59 ||
        x.milliseconds < 0 || x.milliseconds > 999) return false;
    uint64_t days = 0;
    for (int y = 1601; y < x.year; ++y) days += leap(y) ? 366u : 365u;
    for (int m = 1; m < x.month; ++m) days += (unsigned)month_length(x.year, m);
    days += (unsigned)(x.day - 1);
    *out = days * TICKS_DAY +
        ((uint64_t)x.hour * 3600u + (uint64_t)x.minute * 60u +
         (uint64_t)x.second) * TICKS_SECOND +
        (uint64_t)x.milliseconds * UINT64_C(10000);
    return true;
}
static inline bool from_ticks(uint64_t ticks, TimeFields* out) {
    if (!out) return false;
    uint64_t days = ticks / TICKS_DAY;
    uint64_t remainder = ticks % TICKS_DAY;
    int year = 1601;
    while (year <= 9999) {
        const uint64_t len = leap(year) ? 366u : 365u;
        if (days < len) break;
        days -= len;
        ++year;
    }
    if (year > 9999) return false;
    int month = 1;
    while (month <= 12) {
        const uint64_t len = (unsigned)month_length(year, month);
        if (days < len) break;
        days -= len;
        ++month;
    }
    if (month > 12) return false;
    const uint64_t absolute_days = ticks / TICKS_DAY;
    TimeFields x = {};
    x.year = (int16_t)year; x.month = (int16_t)month;
    x.day = (int16_t)(days + 1);
    x.weekday = (int16_t)((absolute_days + 1u) % 7u); // 1601-01-01 was Monday, Sunday=0
    x.hour = (int16_t)(remainder / (3600u * TICKS_SECOND));
    remainder %= 3600u * TICKS_SECOND;
    x.minute = (int16_t)(remainder / (60u * TICKS_SECOND));
    remainder %= 60u * TICKS_SECOND;
    x.second = (int16_t)(remainder / TICKS_SECOND);
    remainder %= TICKS_SECOND;
    x.milliseconds = (int16_t)(remainder / UINT64_C(10000));
    *out = x;
    return true;
}
} // namespace merc360_k1
#endif
