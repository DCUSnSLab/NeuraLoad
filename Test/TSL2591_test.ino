#include <Wire.h>
#include <Adafruit_Sensor.h>
#include "Adafruit_TSL2591.h"

Adafruit_TSL2591 tsl = Adafruit_TSL2591(2591);

void setup() {
  Serial.begin(9600);
  
  //init
  if (tsl.begin()) {
    Serial.println("sensor connected");
  } else {
    Serial.println("sensor not connected");
    while (1);
  }
  // sensor setting
  configureSensor();
}

void configureSensor() {
  // test with various gain
  tsl.setGain(TSL2591_GAIN_MED); // medium gain (25x)

  //측정시간 300ms
  //길수록 정확함
  tsl.setTiming(TSL2591_INTEGRATIONTIME_300MS); // 300ms
  
  Serial.println("=== 센서 설정 정보 ===");
  Serial.print("현재 게인:    ");

  tsl2591Gain_t gain = tsl.getGain(); 
  
  switch(gain) {
    case TSL2591_GAIN_LOW:  Serial.println("1x (Low)"); break; // low gain (1x)
    case TSL2591_GAIN_MED:  Serial.println("25x (Medium)"); break; // medium gain (25x)
    case TSL2591_GAIN_HIGH: Serial.println("428x (High)"); break; // medium gain (428x)
    case TSL2591_GAIN_MAX:  Serial.println("9876x (Max)"); break; // max gain (9876x)
  }
  
  Serial.print("적분 시간:    ");
  Serial.print((tsl.getTiming() + 1) * 100);  // 적분시간 ms로 변환
  Serial.println(" ms");
  
  // read status register
  uint8_t status = tsl.getStatus();

  Serial.print("상태 레지스터: 0x");
  Serial.print(status, HEX);
  Serial.print(" (");
  
  // 1 : 센서가 정상적으로 빛을 측정하고 데이터가 준비되었을 때
  // 0 : 센서가 아직 측정 중이거나 데이터가 준비되지 않았을 때
  if (status & 0x01) 
    Serial.print("\"ALS Valid\" ");

  // 미리 설정한 threshold 범위를 벗어났을 때 1 출력
  if (status & 0x10) 
    Serial.print("\"ALS Interrupt\" ");
  
  //Persist 필터를 무시하고 즉시 발생하는 인터럽트
  //급격한 조도 변화 감지할때 사용
  if (status & 0x20)
    Serial.print("\"No-Persist Int\" ");
  
  Serial.println(")");
  Serial.println();
}


void loop() {

  //부팅 후 경과 시간
  unsigned long currentTime = millis();
  
  // dynamic gain adjustment
  static unsigned long lastAdjustTime = 0;
  if (currentTime - lastAdjustTime >= 5000) {
    Serial.println("check gain");
    tsl2591Gain_t optimalGain = autoAdjustGain();
    lastAdjustTime = currentTime;
  }
  
  //32비트 전체 데이터
  uint32_t fullLuminosity = tsl.getFullLuminosity(); // 32-bit raw count (high word: IR, low word: IR+Visible)
  uint16_t ch0 = fullLuminosity & 0xFFFF; // ch 0 data
  uint16_t ch1 = fullLuminosity >> 16; // ch 1 data
  
  //개별 채널 데이터 (검증용)
  //uint16_t fullSpectrum = tsl.getLuminosity(TSL2591_FULLSPECTRUM); // ch 0 data
  //uint16_t infrared = tsl.getLuminosity(TSL2591_INFRARED); // ch 1 data
  
  //가시광
  //감지된 가시광의 세기
  uint16_t visible = tsl.getLuminosity(TSL2591_VISIBLE);
  
  // Lux 계산 (조도)
  // 조도 : 단위 면적 당 광속의 양
  float lux = tsl.calculateLux(ch0, ch1);
  
  // 전체 파장 중 적외선 비율 계산
  // float ratio = 0;
  // if (ch0 != 0) {
  //   ratio = (float)ch1 / (float)ch0;
  // }
  
  // CPL : 센서 감도
  // 높을때 민감함
  float cpl = calculateCPL();
  
  // 게인 계수 : 신호 증폭 배율
  // 밝은 떄 낮은 게인, 어두울때 높은 게인 사용해야됨
  float gainMultiplier = getGainMultiplier();
  // 적분 시간 : 빛모으는 시간
  float integrationTime = (tsl.getTiming() + 1) * 100.0F;
  
  // API data
  sensors_event_t event;
  tsl.getEvent(&event); //get event data

  // 게인 자동 조정 테스트 (10초마다)
  // if (currentTime % 10000 < 500) {
  //   testAllGainSettings();
  // }
  
  Serial.print("currentTime:");
  Serial.print(currentTime);
  Serial.print("\t");
  Serial.print("lux:");
  Serial.print(lux);
  Serial.print("\t");
  Serial.print("gainMultiplier:");
  Serial.print(gainMultiplier);
  Serial.print("\t");
  Serial.print("integrationTime:");
  Serial.print(integrationTime);
  Serial.print("\t");
  Serial.print("cpl:");
  Serial.print(cpl);
  Serial.print("\t");
  Serial.print("visible:");
  Serial.print(visible);
  Serial.println();
  delay(500);
}

float calculateCPL() {
  float atime, again;
  
  // 적분 시간 계수
  switch (tsl.getTiming()) {
    case TSL2591_INTEGRATIONTIME_100MS: atime = 100.0F; break;  // 100ms
    case TSL2591_INTEGRATIONTIME_200MS: atime = 200.0F; break;  // 200ms
    case TSL2591_INTEGRATIONTIME_300MS: atime = 300.0F; break;  // 300ms
    case TSL2591_INTEGRATIONTIME_400MS: atime = 400.0F; break;  // 400ms
    case TSL2591_INTEGRATIONTIME_500MS: atime = 500.0F; break;  // 500ms
    case TSL2591_INTEGRATIONTIME_600MS: atime = 600.0F; break;  // 600ms
    default: atime = 100.0F; break;
  }
  
  // 게인 계수
  switch (tsl.getGain()) {
    case TSL2591_GAIN_LOW:  again = 1.0F; break;     // low gain (1x)
    case TSL2591_GAIN_MED:  again = 25.0F; break;    // medium gain (25x)
    case TSL2591_GAIN_HIGH: again = 428.0F; break;   // medium gain (428x)
    case TSL2591_GAIN_MAX:  again = 9876.0F; break;  // max gain (9876x)
    default: again = 1.0F; break;
  }
  
  // CPL = (ATIME * AGAIN) / DF
  return (atime * again) / 408.0F;  // TSL2591_LUX_DF = 408.0F (Lux cooefficient)
}

float getGainMultiplier() {
  switch (tsl.getGain()) {
    case TSL2591_GAIN_LOW:  return 1.0F;     // low gain (1x)
    case TSL2591_GAIN_MED:  return 25.0F;    // medium gain (25x)
    case TSL2591_GAIN_HIGH: return 428.0F;   // medium gain (428x)
    case TSL2591_GAIN_MAX:  return 9876.0F;  // max gain (9876x)
    default: return 1.0F;
  }
}


tsl2591Gain_t autoAdjustGain() {
  tsl2591Gain_t originalGain = tsl.getGain();
  tsl2591Gain_t gains[] = {TSL2591_GAIN_LOW, TSL2591_GAIN_MED, TSL2591_GAIN_HIGH, TSL2591_GAIN_MAX};
  
  tsl2591Gain_t bestGain = TSL2591_GAIN_MED;  // 기본값
  int bestScore = -1;

  for (int i = 0; i < 4; i++) {
    // 게인 설정 및 안정화
    tsl.setGain(gains[i]);
    delay(500);
    // 측정
    uint32_t lum = tsl.getFullLuminosity();
    uint16_t ch0 = lum & 0xFFFF;
    uint16_t ch1 = lum >> 16;
    float lux = tsl.calculateLux(ch0, ch1);

    // 게인 품질 평가
    int score = 0;
    // 1. 포화 상태 또는 사용불가
    if (ch0 >= 65535 || ch1 >= 65535 || lux < 0 || ch0 < 100) {
    score = 0;  // 사용불가
    }
    // 2. 최적 범위 (가장 안정적이고 정확)
    else if (ch0 >= 2000 && ch0 <= 30000) {
    score = 100;  // 최고 품질
    }
    // 3. 사용 가능 범위 (약간의 오차 허용)
    else if (ch0 >= 500 && ch0 <= 50000) {
    score = 60;  // 중간 품질
    }
    // 4. 위험 구간 (포화 임박 또는 노이즈)
    else {
    score = 20;  // 낮은 품질
    }

    // 최적 게인 선택
    if (score > bestScore) {
      bestGain = gains[i];
      bestScore = score;
    }

    // 최적 범위를 찾으면 더 이상 검색하지 않음 (효율성)
    if (score == 100) {
      break;
    }
  }
  // 최적 게인 적용
  tsl.setGain(bestGain);
  Serial.println("bestGain:");
  Serial.println(getGainMultiplier());
  return bestGain;
}