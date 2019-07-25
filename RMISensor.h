/*
UC Davis RMI Sensor Project
Driver header file
Written by Nick Madrid
*/

#include <project.h>
#include <FS.h>
#include <stdbool.h>
#include <unistd.h>

#ifndef RMISENSOR_H_INCLUDED
#define RMISENSOR_H_INCLUDED

#define     BOARD_SELECT       0    // 0=satellite 1=wired 2=dust
#define     COMM_SELECT        0    // 0=XBee 1=BLE
#define     SD_ENABLE          0    // 0=DisableSD 1=EnableSD
#define     WAKE_INTERVAL      2   // Wake interval in minutes 15(original) -->2
#define     TIMEOUT_PERIOD     10   //1 second Change to 100 instead of 10(original)    
#define     DUST_ARRAY_SIZE    150


#if(BOARD_SELECT == 0)
    #define     DATA_ARRAY_SIZE         15
    #define     CHECKSUM_ARRAY_SIZE     15    
#elif(BOARD_SELECT == 1)
    #define     DATA_ARRAY_SIZE         17
    #define     CHECKSUM_ARRAY_SIZE     17
#elif(BOARD_SELECT == 2)
    #define     DATA_ARRAY_SIZE         17
    #define     CHECKSUM_ARRAY_SIZE     167
#endif

volatile uint8 wake_flag;
bool sync_flag; //used to be before change to boolean
volatile uint8 dust_flag;
volatile int timeoutTimer;

int nodeDelay;//What I added to get node ID delay

FS_FILE * sdFile;
uint8 tempDustArray[12];
uint8 dataArray[DATA_ARRAY_SIZE];
uint8 dustArray[DUST_ARRAY_SIZE];
uint8 checksumArray[CHECKSUM_ARRAY_SIZE];
uint8 year, month, day, hour, minute, sec;
uint8 waitMinutes;
uint8 intvl;
uint8 count;
char dataFile[12];
uint8 i;
int lineCount;
    
void oneSecSleep(uint8);
void sleepSensors();
void wakeSensors();
void sleepXBee();
void wakeXBee();
void sleepTimer();
void wakeTimer();
void sleepADC();
void wakeADC();
void sleepSD();
void wakeSD();

void getNodeID(); //New scatter idea
void syncRTC_XBee();
void syncRTC_BLE();
void getData();
void readCozir();
void readVOC();
void readDust();
void sendData();
void sendDataSleep(uint8);
void sendLoggedData();
uint8 getChecksum();
void checkBattery();
void write2SD();
void getTime();

#endif

/* [] END OF FILE */
