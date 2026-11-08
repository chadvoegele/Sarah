package com.serexe.sarah

import org.junit.Assert.*
import org.junit.Test

class TimerCountdownTest {
 @Test fun roundsUpAndShowsHoursWithoutInventingExpiry() {
  assertEquals("00:01",TimerCountdown.remaining(1001,1000))
  assertEquals("02:00",TimerCountdown.remaining(120000,1))
  assertEquals("1:01:01",TimerCountdown.remaining(3661000,0))
  assertEquals("Due now",TimerCountdown.remaining(1000,1000))
  assertEquals("Due now",TimerCountdown.remaining(999,1000))
 }
}
