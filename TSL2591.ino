#include <Wire.h>
#include <Adafruit_Sensor.h>
#include "Adafruit_TSL2591.h"

Adafruit_TSL2591 tsl = Adafruit_TSL2591(2591);

void setup() {
  Serial.begin(9600);
  
  //init
  // if (tsl.begin()) {
  //   //Serial.println("sensor connected");
  // } else {
  //   Serial.println("sensor not connected");
  // }
  
  // sensor setting
  configureSensor();
}

void configureSensor() {
  tsl.setGain(TSL2591_GAIN_MED); // medium gain (25x)
  tsl.setTiming(TSL2591_INTEGRATIONTIME_300MS); // 300ms
}


void loop() {
  unsigned long currentTime = millis();
  
  // 게인 자동 조정 (5초마다)
  static unsigned long lastAdjustTime = 0;
  if (currentTime - lastAdjustTime >= 10000) {
    autoAdjustGain();
    lastAdjustTime = currentTime;
  }
  
  // 센서 데이터 수집
  uint32_t fullLuminosity = tsl.getFullLuminosity();
  uint16_t ch0 = fullLuminosity & 0xFFFF;
  uint16_t ch1 = fullLuminosity >> 16;
  uint16_t visible = tsl.getLuminosity(TSL2591_VISIBLE);
  float lux = tsl.calculateLux(ch0, ch1);
  float cpl = calculateCPL();
  float gainMultiplier = getGainMultiplier();
  float integrationTime = (tsl.getTiming() + 1) * 100.0F;
  
  
  Serial.print(currentTime); // timestamp
  Serial.print(",");
  Serial.print(lux); // 조도
  Serial.print(",");
  Serial.print(gainMultiplier); //gain
  Serial.print(",");
  Serial.print(integrationTime); //적분 시간
  Serial.print(",");
  Serial.print(cpl); //룩스 당 카운트 값
  Serial.print(",");
  Serial.print(visible); //가시광선 강도
  Serial.print(",");
  Serial.print(ch0); // ch0
  Serial.print(",");
  Serial.print(ch1); // ch1
  Serial.print(",");
  Serial.println(fullLuminosity); // 전체 광도
  
  delay(500);
}

float calculateCPL() {
  float atime, again;
  
  switch (tsl.getTiming()) {
    case TSL2591_INTEGRATIONTIME_100MS: atime = 100.0F; break;
    case TSL2591_INTEGRATIONTIME_200MS: atime = 200.0F; break;
    case TSL2591_INTEGRATIONTIME_300MS: atime = 300.0F; break;
    case TSL2591_INTEGRATIONTIME_400MS: atime = 400.0F; break;
    case TSL2591_INTEGRATIONTIME_500MS: atime = 500.0F; break;
    case TSL2591_INTEGRATIONTIME_600MS: atime = 600.0F; break;
    default: atime = 100.0F; break;
  }
  
  switch (tsl.getGain()) {
    case TSL2591_GAIN_LOW:  again = 1.0F; break;
    case TSL2591_GAIN_MED:  again = 25.0F; break;
    case TSL2591_GAIN_HIGH: again = 428.0F; break;
    case TSL2591_GAIN_MAX:  again = 9876.0F; break;
    default: again = 1.0F; break;
  }
  
  return (atime * again) / 408.0F;
}

float getGainMultiplier() {
  switch (tsl.getGain()) {
    case TSL2591_GAIN_LOW:  return 1.0F;
    case TSL2591_GAIN_MED:  return 25.0F;
    case TSL2591_GAIN_HIGH: return 428.0F;
    case TSL2591_GAIN_MAX:  return 9876.0F;
    default: return 1.0F;
  }
}

void autoAdjustGain() {
  tsl2591Gain_t gains[] = {TSL2591_GAIN_LOW, TSL2591_GAIN_MED, TSL2591_GAIN_HIGH, TSL2591_GAIN_MAX};
  tsl2591Gain_t bestGain = TSL2591_GAIN_MED;
  int bestScore = -1;

  for (int i = 0; i < 4; i++) {
    tsl.setGain(gains[i]);
    delay(100);
    
    uint32_t lum = tsl.getFullLuminosity();
    uint16_t ch0 = lum & 0xFFFF;
    
    int score = 0;
    if (ch0 >= 65535 || ch0 < 100) {
      score = 0;
    } else if (ch0 >= 2000 && ch0 <= 30000) {
      score = 100;
    } else if (ch0 >= 500 && ch0 <= 50000) {
      score = 60;
    } else {
      score = 20;
    }

    if (score > bestScore) {
      bestGain = gains[i];
      bestScore = score;
    }

    if (score == 100) break;
  }
  
  tsl.setGain(bestGain);
}