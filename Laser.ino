void setup() {
  Serial.begin(9600);
  Serial2.begin(115200);  // 레이저 센서와 통신
  // uint8_t fr_checksum = 0x5A + 0x06 + 0x03 + 0x0A + 0x00; // frame rate 조절 10hz
  // uint8_t set_fr_command[] = { 0x5A, 0x06, 0x03, 0x0A, 0x00, fr_checksum };  // frame rate 조절
  // laserSerial.write(set_fr_command, sizeof(set_fr_command));        // 명령어 전송

  // uint8_t checksum = 0x5A + 0x05 + 0x05 + 0x06;
  // uint8_t set_mm_command[] = { 0x5A, 0x05, 0x05, 0x06, checksum };  // mm로 설정
  // laserSerial.write(set_mm_command, sizeof(set_mm_command));        // 명령어 전송

  // uint8_t set_sv_command[] = { 0x5A, 0x04, 0x11, 0x6F};  // save command
  // laserSerial.write(set_sv_command, sizeof(set_sv_command));        // 명령어 전송
}

void loop() {
  if (Serial2.available() >= 9) {  // 9바이트 데이터 수신 확인
    uint8_t buf[9];
    for (int i = 0; i < 9; i++) {
      buf[i] = Serial2.read();  // 레이저 센서로부터 데이터 읽기
    }

    // 패킷 시작 확인
    if (buf[0] == 0x59 && buf[1] == 0x59) {
      int distance = buf[2] + (buf[3] << 8);  // 거리
      int strength = buf[4] + (buf[5] << 8);
      float temperature = ((buf[7] << 8) | buf[6]) / 80;
      // 아두이노 시리얼 모니터에도 거리 데이터 출력
      Serial.print(distance);
      Serial.print(',');
      Serial.print(strength);
      Serial.print(',');
      Serial.println(temperature);
    }
  }
}
