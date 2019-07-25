/*
UC Davis RMI Sensor Project
Driver source file
Written by Nick Madrid
*/

#include "RMISensor.h"
#include <stdio.h>

// Sleep for specified period of time
void oneSecSleep(uint8 sleepTime) {
    #if(BOARD_SELECT == 0)
        for (i = 0; i < sleepTime; i++) {
            CyPmSaveClocks();
            CyPmSleep(PM_SLEEP_TIME_NONE, PM_SLEEP_SRC_ONE_PPS);
            CyPmRestoreClocks();       
        }
    #else   
        CyDelay(sleepTime * 1000);         
    #endif
}

// Put sensors to sleep
void sleepSensors() {
    Reg_SHDN_Write(0);     
    COZIR_Stop();
    #if (BOARD_SELECT != 0)    
        VOC_Stop();
    #endif
}

// Wake sensors up
void wakeSensors() {
    Reg_SHDN_Write(1);    
    COZIR_Start();
    #if (BOARD_SELECT != 0)
        VOC_Start();
    #endif
}

// Put XBee to sleep
void sleepXBee() {
    XBee_SHDN_Write(1);
    XBee_Stop();    
}

// Wake XBee up
void wakeXBee() {
    XBee_SHDN_Write(0);
    XBee_Start();    
}

// Put timer to sleep
void sleepTimer() {
    isr_ms_Stop();
    Timer_100ms_Stop();       
}

// Wake timer up
void wakeTimer() {
    isr_ms_Start();
    Timer_100ms_Start();   
}

// Put ADC to sleep
void sleepADC() {
    Battery_SHDN_Write(0);     
    Opamp_Stop();
    Battery_ADC_Stop();
    Battery_ADC_StopConvert();     
}

// Wake ADC up
void wakeADC() {
    Battery_SHDN_Write(1);    
    Opamp_Start();
    Battery_ADC_Start();
    Battery_ADC_StartConvert(); 
}

// Put SD card to sleep
void sleepSD() {
    SD_SHDN_Write(0);
    emFile_Sleep();
    emFile_miso0_Write(0);
    emFile_mosi0_Write(0);
    emFile_sclk0_Write(0);
    emFile_SPI0_CS_Write(0);    
}

// Wake SD card up
void wakeSD() {
    SD_SHDN_Write(1);
    emFile_Wakeup();    
    emFile_miso0_Write(1);
    emFile_mosi0_Write(1);
    emFile_sclk0_Write(1);
    emFile_SPI0_CS_Write(1);    
}
/* This is code that will get a node ID to help stagger node in sending data*/
void getNodeID() {
    uint8 done, retry, RX_count, nodeID[2];
    int temp;
    done = 0;
    retry = 0;
    
    while(done != 1) {
        XBee_ClearRxBuffer();
        XBee_PutChar('p');
        RX_count = 0;
        timeoutTimer = 0;
        while (timeoutTimer < TIMEOUT_PERIOD && RX_count < 2) {
            RX_count = XBee_GetRxBufferSize();
            CyDelay(15);
        }
        if (RX_count > 0) {
            done = 1;
        }
        else if (retry < 50) {
            retry++;
        }
        else {
            sleepXBee();
            sleepTimer();
            oneSecSleep(2); //originally 180
            CySoftwareReset();
        } 
    }
    for(i = 0; i < 2; i++){
        nodeID[i] = XBee_GetChar();
    }
    //nodeID = nodeID - 48;
    
    temp = nodeID[1] - 48;
    temp = temp + (nodeID[0]-48)*10;
    nodeDelay = (temp - 9) * 5;   
}

// Use XBee to sync the RTC with the gateway
void syncRTC_XBee() {
    uint8 time[12];
    uint8 done, retry, RX_count;
    done = 0;
    retry = 0;
    
    while(done != 1) {
        XBee_ClearRxBuffer();
        XBee_PutChar('c');
        RX_count = 0;
        timeoutTimer = 0;
        while (timeoutTimer < TIMEOUT_PERIOD && RX_count < 12) {
            RX_count = XBee_GetRxBufferSize();
        }
        if (RX_count > 11) {
            done = 1;
        }
        else if (retry < 5) {
            retry++;
        }
        else {
            sleepXBee();
            sleepTimer();
            oneSecSleep(5); //originally 180
            CySoftwareReset();
        }
    }
    for (i = 0; i < 12; i++){
        time[i] = XBee_GetChar();
    }
    
    RTC_WriteYear((time[0]-48)*10+(time[1]-48));
    RTC_WriteMonth((time[2]-48)*10+(time[3]-48));
    RTC_WriteDayOfMonth((time[4]-48)*10+(time[5]-48));
    RTC_WriteHour((time[6]-48)*10+(time[7]-48));
    RTC_WriteMinute((time[8]-48)*10+(time[9]-48));
    RTC_WriteSecond((time[10]-48)*10+(time[11]-48));
    
    uint8 minute = RTC_ReadMinute();
    while (minute >= WAKE_INTERVAL) {
        minute -= WAKE_INTERVAL;
    }
    
    waitMinutes = WAKE_INTERVAL - minute;
}

// Use BLE module to sync the RTC with the gateway
void syncRTC_BLE() {
    uint8 time[12];
    while(PSoC4_GetRxBufferSize() < 12) {}
    for (i = 0; i < 12; i++) {
        time[i] = PSoC4_GetByte();
    }
    RTC_WriteYear((time[0]-48)*10+(time[1]-48));
    RTC_WriteMonth((time[2]-48)*10+(time[3]-48));
    RTC_WriteDayOfMonth((time[4]-48)*10+(time[5]-48));
    RTC_WriteHour((time[6]-48)*10+(time[7]-48));
    RTC_WriteMinute((time[8]-48)*10+(time[9]-48));
    RTC_WriteSecond((time[10]-48)*10+(time[11]-48));
    
    uint8 minute = RTC_ReadMinute();
    while (minute >= WAKE_INTERVAL) {
        minute -= WAKE_INTERVAL;
    }
    
    waitMinutes = WAKE_INTERVAL - minute;
}

// Call the functions required to get the sensor data
void getData() {
    getTime();
    readCozir();
    #if (BOARD_SELECT == 1 || BOARD_SELECT == 2)
        readVOC();
    #endif   
}

// Get data from the COZIR sensor
void readCozir() {
    uint8 arrayIndex = 0, done = 0, RX_count;
    uint8 sensorByte;

    for (i = 0; i < 15; i++) {
        dataArray[i] = 48;   
    }    
    //CyDelay(50);  //This delay removes issue with ghost write of sync_flag
    while (done != 1) {
        RX_count = 0;
        COZIR_ClearRxBuffer();
        COZIR_PutString("Q\r\n");
        timeoutTimer = 0;
        while(timeoutTimer < TIMEOUT_PERIOD && RX_count < 25) {
            RX_count = COZIR_GetRxBufferSize();
        }
        if(RX_count > 24){
            done = 1;
        }
    }
    for (int i = 0; i < 25; i++){
        sensorByte = COZIR_GetByte();
        if (sensorByte > 47 && sensorByte < 58) {
            dataArray[arrayIndex++] = sensorByte;
        }
        else if (sensorByte == '\n') {
        //nothing
        }
    }
        
}

// Get data from the VOC sensor
void readVOC() {  
    const uint8 SLAVE_ADDR = 90;
    uint8 readBuffer[2];
    uint8 *readPtr = &readBuffer;    
    
    readBuffer[0] = 48;     readBuffer[1] = 48;
    VOC_MasterReadBuf(SLAVE_ADDR, readPtr, 2, VOC_MODE_COMPLETE_XFER);
    timeoutTimer = 0;
    while((VOC_MasterStatus() & 0x01) != 1 && timeoutTimer < TIMEOUT_PERIOD);
    dataArray[15] = readBuffer[0];
    dataArray[16] = readBuffer[1];
}

// Get data from the dust sensor
void readDust() {
    uint8 DustData;
    uint8 tempBuf[5];
    uint8 flg = 0;
    uint8 v;
    uint8 dif;
    uint8 k;
    
    for (i = 0; i < 5; i++) {
        tempBuf[i] = 48;   
    }
    
    for (i = 0; i < count; i++) {
        DustData = tempDustArray[i];
        if (DustData==',' || DustData=='\r') {
            dif=intvl-flg;
            v=0;
            while(dif<intvl) {
                dustArray[dif]=tempBuf[v];
                dif++;
                v++;
            }
            intvl=intvl+5;
            flg=0;
            for (k = 0; k < 5; k++) {
                tempBuf[k] = 48;
            }
        }
        else {
            tempBuf[flg]=DustData;
            flg++;
        }
    }
}

// Send the sensor data with the XBee
void sendData() {
    uint8 sendArray[DATA_ARRAY_SIZE + 1];
    uint8 errorCheck;
    uint8 done, retry;
    
    for (i = 0; i < DATA_ARRAY_SIZE; i++) {
        checksumArray[i] = dataArray[i];
        sendArray[i + 1] = dataArray[i];
    }
    #if(BOARD_SELECT == 2)
        for (i = 0; i < DUST_ARRAY_SIZE; i++) {
            checksumArray[i+17] = dustArray[i]; 
        }
    #endif
    sendArray[0] = getChecksum();
    
    retry = 1;
    while(retry > 0) {
        if (retry > 5) {
            #if (SD_ENABLE == 1)
                wakeSD();
                write2SD();
                sleepSD();
            #endif
            break;            
        }

        XBee_ClearRxBuffer();
        XBee_PutArray(sendArray, DATA_ARRAY_SIZE + 1);
        #if(BOARD_SELECT == 2)       
            CyDelay(50);
            XBee_PutArray(dustArray, DUST_ARRAY_SIZE);
        #endif
        
        timeoutTimer = 0;
        done = 0;
        while(timeoutTimer < TIMEOUT_PERIOD && done != 1) {
            if (XBee_GetRxBufferSize() > 0) {
                errorCheck = XBee_GetChar();
                if (errorCheck == 'g') {
                    #if (SD_ENABLE == 1)
                        if (lineCount > 0) {
                            wakeSD();
                            sendLoggedData();
                            sleepSD();
                        }
                    #endif
                    
                    done = 1;                    
                    retry = 0;
                    #if(BOARD_SELECT == 2)    
                        for (i = 0; i < DUST_ARRAY_SIZE; i++) {
                            dustArray[i] = 48;
                        }
                        intvl = 5;
                    #endif
                }
                else if (errorCheck == 'm') {
                    done = 1;
                    retry++;
                    sendDataSleep(3);
                }
                else if (errorCheck == 'i') {
                    done = 1;
                    retry++;
                    sendDataSleep(6);
                }
            }
        }
        if (done == 0) {
            retry++; 
            sendDataSleep(9);
        }
    }
}

// Sleep during sending of sensor data in the event of transmission errors
void sendDataSleep(uint8 sleepTime) {
    sleepXBee();
    sleepTimer();
    oneSecSleep(sleepTime);   
    wakeXBee();
    wakeTimer(); 
    CyDelay(15);    
}

// Send logged sensor data from the SD card
void sendLoggedData() {
    uint8 linesToSend;
    if (lineCount > 10)
        linesToSend = 10;
    else
        linesToSend = lineCount;
    
    XBee_ClearRxBuffer();
    XBee_PutChar('r');
    XBee_PutChar(linesToSend);
    
    uint8 done = 0;
    timeoutTimer = 0;
    while(timeoutTimer < TIMEOUT_PERIOD && done != 1) {
        if (XBee_GetRxBufferSize() > 0) {
            uint8 rcvByte = XBee_GetChar();
            if (rcvByte == 'o')
                done = 1;
        }   
    }
    
    if (done) {
        FS_Init();
        FS_FILE * sd_tempFile;
        
        uint8 line[DATA_ARRAY_SIZE + 10];
        
        sdFile = FS_FOpen(dataFile, "r");
        if(sdFile)
        {   
            sd_tempFile = FS_FOpen("Temp.txt", "w");
            uint8 SD_readCount = 0;
            while (FS_Read(sdFile, line, (DATA_ARRAY_SIZE + 12)) > 0) {
                if (SD_readCount < linesToSend) {
                    XBee_PutArray(line, DATA_ARRAY_SIZE + 10);
                    CyDelay(50);
                    SD_readCount++;
                    lineCount--;
                }
                else {
                    if(sd_tempFile)
                    {
                        FS_Write(sd_tempFile, line, DATA_ARRAY_SIZE + 10);
                        FS_Write(sd_tempFile, "\r\n", 2);
                    }
                }
            }
            FS_FClose(sd_tempFile);
        }
        FS_FClose(sdFile);
        FS_Remove(dataFile);
        
        FS_Rename("Temp.txt", dataFile);
        
        FS_DeInit();
    }
}

// Get the current sensor data's checksum
uint8 getChecksum() {
    uint8 checksum;
    uint16 checksumTotal = 0;
    
    for (i = 0; i < CHECKSUM_ARRAY_SIZE; i++) {
        checksumTotal += checksumArray[i];
    }
    checksum = checksumTotal % 256;
    
    return checksum;  
}

// Send the current battery measurement
void checkBattery() {
    uint16 batteryOut;
    uint16 batteryVoltage; 
    
    uint8 status = Battery_ADC_IsEndConversion(Battery_ADC_RETURN_STATUS);
    batteryOut = Battery_ADC_GetResult16();
    status = 0;
    timeoutTimer = 0; 
    while (status == 0 && timeoutTimer < TIMEOUT_PERIOD) {
        status = Battery_ADC_IsEndConversion(Battery_ADC_RETURN_STATUS);
    }
    if (status != 0) {
        batteryOut = Battery_ADC_GetResult16();
        batteryVoltage = batteryOut * (3.3 / 4096) * 200;
  
        char battery_outstring[3];
        sprintf(battery_outstring, "%d", batteryVoltage);
  
        XBee_PutString(battery_outstring);
    }
}

// Write sensor data to the SD card
void write2SD() {
    char strYear[2], strMonth[2], strDay[2], strHour[2], strMin[2];
    uint8 timeArray[10];
    
    sprintf(strYear, "%02d", year);
    sprintf(strMonth, "%02d", month);
    sprintf(strDay, "%02d", day);
    sprintf(strHour, "%02d", hour);
    sprintf(strMin, "%02d", minute);    
    timeArray[0] = strYear[0];    timeArray[1] = strYear[1];
    timeArray[2] = strMonth[0];   timeArray[3] = strMonth[1];
    timeArray[4] = strDay[0];     timeArray[5] = strDay[1];
    timeArray[6] = strHour[0];    timeArray[7] = strHour[1];
    timeArray[8] = strMin[0];     timeArray[9] = strMin[1]; 
    
    FS_Init();
    sdFile = FS_FOpen(dataFile, "a");
    if(sdFile)
    {   
        if(0 != FS_Write(sdFile, timeArray, 10)) 
        {
            FS_Write(sdFile, dataArray, DATA_ARRAY_SIZE);
            FS_Write(sdFile, "\r\n", 2);
            lineCount++;
        }
    }
    FS_FClose(sdFile);
    FS_DeInit();    
}

// Get current RTC time
void getTime() {
    year = RTC_ReadYear();
    month = RTC_ReadMonth();
    day = RTC_ReadDayOfMonth();
    hour = RTC_ReadHour();
    minute = RTC_ReadMinute();
    sec = RTC_ReadSecond();
}

/* [] END OF FILE */
