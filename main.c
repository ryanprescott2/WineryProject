/*
UC Davis RMI Sensor Project
Main file for PSoC 5LP-108
Written by Nick Madrid
*/

#include "RMISensor.h"

int main()
{
    // Initialize SD card file and flags to 0
    #if (SD_ENABLE == 1)
        strcpy(dataFile, "Data.txt");
    #endif 
    wake_flag = 0;
    sync_flag = false;
    dust_flag = 0;
    lineCount = 0;
    
    // Start the initial RTC blocks and watchdog timer
    CyGlobalIntEnable;
    RTC_Start();
 	RTC_WriteIntervalMask(RTC_INTERVAL_SEC_MASK | RTC_INTERVAL_MIN_MASK | RTC_INTERVAL_DAY_MASK);
    //The watch dog time is commented out for testing O: uncommented
    //CyWdtStart(CYWDT_1024_TICKS, CYWDT_LPMODE_NOCHANGE); //Cy  stands for Cypress
    sleepADC();
    sleepSD();
    
    // Perform RTC sync using XBee or BLE module depending on board communication type
    #if (COMM_SELECT == 0)
        wakeXBee();
        wakeTimer();
        CyDelay(15);   //was 15
        //XBee_PutChar('l'); //This is to test
        //CyDelay(50);
        
        syncRTC_XBee();    //CALLS Clock
        getNodeID();       // This is a function made to help spread nodes 
    #elif (COMM_SELECT == 1)
        PSoC4_Start();
        syncRTC_BLE();
    #endif

    sleepXBee();
    sleepTimer();
    
    // Configure COZIR sensor settings
    wakeSensors();      
    CyDelay(10);
    COZIR_PutString("K 2\r\n");         // Set COZIR for polling mode
    CyDelay(10);
    COZIR_PutString("A 4\r\n");         // Set COZIR warmup time for 5 seconds
    CyDelay(10);
    COZIR_PutString("M 4164\r\n");      // Set COZIR to take temperature, relative humidity, and CO2 measurements
    CyDelay(10);
    sleepSensors();
    
    // Initialize dust sensor settings
    #if(BOARD_SELECT == 2)
        Dust_Start();     
        isr_dust_Start();
        for (i = 0; i < DUST_ARRAY_SIZE; i++) {
            dustArray[i] = 48;   
        }
        intvl = 5;
        count = 0;    
    #endif
        
    for(;;) {
        // Get data from dust sensor
        if (dust_flag) {
            readDust();
            dust_flag = 0;
            count = 0;
        }
        
        // Perform measurement cycle when RTC wakes the device up
        if (wake_flag) {
            wake_flag = 0;
            
            // Wake sensors and get sensor data
            wakeSensors();
            wakeTimer();
            oneSecSleep(5);     // Sleep for 5 seconds for COZIR warmup time 
            getData(); //Takes sensor readings 
            sleepSensors();

            // If XBee node, send sensor data using XBee
            #if (COMM_SELECT == 0)
                wakeXBee();
                CyDelay(15);
                oneSecSleep(nodeDelay);
                sendData(); //Sends the data 
                
                // Sync RTC every midnight
                if (sync_flag) {
                    sync_flag = false;
                    
                    // Send battery data if board is a satellite node
                    #if(BOARD_SELECT == 0)
                        wakeADC();
                        CyDelay(15);
                        checkBattery();
                        sleepADC();
                    #endif

                    CyDelay(5);
                    //XBee_PutChar('p'); //This is to test
                    //CyDelay(50);
                    syncRTC_XBee();  //2nd call of clock
                }
                sleepXBee();
                
            // If BLE node, store sensor data locally on SD card
            #elif (COMM_SELECT == 1)
                wakeSD();
                write2SD();
                sleepSD();
            #endif
            
            sleepTimer();
        }
        
        oneSecSleep(1);     // Sleep for 1 second
    }
    
    return 0;
}

/* [] END OF FILE */
