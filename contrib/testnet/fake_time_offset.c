/* LD_PRELOAD shim for tests: shifts time() by FAKE_TIME_OFFSET seconds, to simulate
 * a node whose clock is wrong.  Build: gcc -shared -fPIC -O2 -o fake_time_offset.so fake_time_offset.c */
#define _GNU_SOURCE
#include <stdlib.h>
#include <time.h>

time_t time(time_t *out)
{
  static int init = 0;
  static long offset = 0;
  if (!init)
  {
    const char *e = getenv("FAKE_TIME_OFFSET");
    offset = e ? atol(e) : 0;
    init = 1;
  }
  struct timespec ts;
  clock_gettime(CLOCK_REALTIME, &ts);
  time_t r = ts.tv_sec + offset;
  if (out)
    *out = r;
  return r;
}
