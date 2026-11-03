#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#define TARGET_IP "192.168.1.100"
#define PORT 8080
#define BUFFER_SIZE 64

int main(){

    int sockfd;
    struct sockaddr_in server_addr;
    char buffer[BUFFER_SIZE];

    double t = 0.0;
    double delta_t = 0.1;
    double y;

    //udp socket oluşturma
    if((sockfd = socket(AF_INET,SOCK_DGRAM,0))<0){

        perror("soket olusturulamadi");
        exit(EXIT_FAILURE);

    }

    memset(&server_addr,0,sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);
    server_addr.sin_addr.s_addr = inet_addr(TARGET_IP);

    printf("veri iletisimi basliyor\n");

    while(1){

        y = pow(t,2.0);
        snprintf(buffer,BUFFER_SIZE,"%.2f",y);

        //veri iletimi
        sendto(sockfd,(const char *)buffer, strlen(buffer), MSG_CONFIRM,
        (const struct sockaddr *) &server_addr, sizeof(server_addr));

        t+=delta_t;
        usleep(100000);

    }
    close(sockfd);
    return 0;

}