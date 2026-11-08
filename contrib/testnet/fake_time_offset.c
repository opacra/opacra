/* LD_PRELOAD shim for tests: shifts time() by FAKE_TIME_OFFSET seconds, to simulate
 * a node whose clock is wrong.  Build: gcc -shared -fPIC -O2 -o fake_time_offset.so fake_time_offset.c
 *
 * FAKE_TIME_OFFSET_FILE (optional) names a file holding the offset; it is re-read at most once a
 * second, so a test can step a running node's clock (as an NTP correction does).  Without the
 * file, or while it is missing, FAKE_TIME_OFFSET applies. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

time_t time(time_t *out)
{
  static int init = 0;
  static long offset = 0;
  static long env_offset = 0;
  static const char *file = NULL;
  static time_t last_read = 0;
  if (!init)
  {
    const char *e = getenv("FAKE_TIME_OFFSET");
    env_offset = offset = e ? atol(e) : 0;
    file = getenv("FAKE_TIME_OFFSET_FILE");
    init = 1;
  }
  if (file)
  {
    struct timespec mono;
    clock_gettime(CLOCK_MONOTONIC, &mono);
    if (mono.tv_sec != last_read)
    {
      last_read = mono.tv_sec;
      long v = env_offset;
      FILE *f = fopen(file, "r");
      if (f)
      {
        if (fscanf(f, "%ld", &v) != 1)
          v = env_offset;
        fclose(f);
      }
      offset = v;
    }
  }
  struct timespec ts;
  clock_gettime(CLOCK_REALTIME, &ts);
  time_t r = ts.tv_sec + offset;
  if (out)
    *out = r;
  return r;
}
