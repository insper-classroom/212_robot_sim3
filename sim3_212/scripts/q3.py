#! /usr/bin/env python3
# -*- coding:utf-8 -*-

# Rodar com 
# roslaunch my_simulation cubos.launch


from __future__ import print_function, division
import rospy
import numpy as np
import numpy
import tf
import math
import cv2
import time
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, CompressedImage, LaserScan
from cv_bridge import CvBridge, CvBridgeError
from numpy import linalg
from tf import transformations
from tf import TransformerROS
import tf2_ros
from geometry_msgs.msg import Twist, Vector3, Pose, Vector3Stamped

from nav_msgs.msg import Odometry
from std_msgs.msg import Header


import visao_module


bridge = CvBridge()

cv_image = None
media = []
centro = []

area = 0.0 # Variavel com a area do maior contorno

resultados = [] # Criacao de uma variavel global para guardar os resultados vistos

x = 0
y = 0
z = 0 
id = 0


# A função a seguir é chamada sempre que chega um novo frame
def roda_todo_frame(imagem):
    #print("frame")
    global cv_image
    global media
    global centro
    global resultados

    now = rospy.get_rostime()
    imgtime = imagem.header.stamp
    lag = now-imgtime # calcula o lag
    delay = lag.nsecs

    try:
        temp_image = bridge.compressed_imgmsg_to_cv2(imagem, "bgr8")
        cv_image = temp_image.copy()
    except CvBridgeError as e:
        print('ex', e)

MARGEM = 50

COR_MENOR_VERMELHO = (0/2, 50,50)
COR_MAIOR_VERMELHO = (20/2, 255, 255)
COR_MENOR_VERDE = (80/2, 50, 50)
COR_MAIOR_VERDE = (150/2, 255, 255)
COR_MENOR_CIANO = (150/2, 50, 50)
COR_MAIOR_CIANO = (190/2, 255, 255)
COR_MENOR_AMARELO = (30/2, 50, 50)
COR_MAIOR_AMARELO = (80/2, 255, 255)

COR_MENOR_LISTA = [COR_MENOR_VERDE, COR_MENOR_AMARELO, COR_MENOR_CIANO, COR_MENOR_VERMELHO]
COR_MAIOR_LISTA = [COR_MAIOR_VERDE, COR_MAIOR_AMARELO, COR_MAIOR_CIANO, COR_MAIOR_VERMELHO]

ESTADO_PROCURA_COR = 0
ESTADO_CENTRALIZAR_COR = 1
ESTADO_AVANCAR_COR = 2

class Estados:

    def __init__(self):

        self.estado = ESTADO_PROCURA_COR
        self.indice_cor = 0

        self.ranges = []

        self.x = 0
        self.y = 0
        self.z = 0
        self.theta = 0
        self.ultimo_tempo = time.time()

        self.ultimo_x = None
        self.ultimo_y = None
        self.distancia = 0

        self.scanner = rospy.Subscriber("/scan", LaserScan, self.recebe_scan)
        self.odom = rospy.Subscriber("/odom", Odometry, self.recebe_odom)

    def recebe_scan(self, message):
        self.ranges = message.ranges

    def recebe_odom(self, dado):
        self.x = dado.pose.pose.position.x
        self.y = dado.pose.pose.position.y
        self.z = dado.pose.pose.position.z
        quat = dado.pose.pose.orientation
        lista = [quat.x, quat.y, quat.z, quat.w]
        angulos = np.degrees(transformations.euler_from_quaternion(lista))
        self.theta = angulos[2]

        if self.ultimo_x is not None:
            self.distancia += ((self.x-self.ultimo_x)**2 + (self.y-self.ultimo_y)**2)**0.5
            print("Distancia: ", self.distancia)

        self.ultimo_x = self.x
        self.ultimo_y = self.y

    # Procurando a cor de interesse

    def procura_cor(self):
        
        if cv_image is not None:
            centro, media, maior_contorno_area = visao_module.identifica_cor(cv_image, COR_MENOR_LISTA[self.indice_cor], COR_MAIOR_LISTA[self.indice_cor])

            print(maior_contorno_area)

            # Nao achou a cor:
            if maior_contorno_area < 1000:
                vel = Twist(Vector3(0,0,0), Vector3(0,0,0.3))
                velocidade_saida.publish(vel)
                return ESTADO_PROCURA_COR
            else: return ESTADO_CENTRALIZAR_COR

        return ESTADO_PROCURA_COR

    def centraliza_cor(self):

        if cv_image is not None:
            centro, media, maior_contorno_area = visao_module.identifica_cor(cv_image, COR_MENOR_LISTA[self.indice_cor], COR_MAIOR_LISTA[self.indice_cor])

            if maior_contorno_area > 1000 :
                if abs(media[0] - centro[0]) > 50:
                    erro = media[0] - centro[0]
                    vel = Twist(Vector3(0.15,0,0), Vector3(0,0,-erro/400))
                    velocidade_saida.publish(vel)
                    return ESTADO_CENTRALIZAR_COR
                else: return ESTADO_AVANCAR_COR
            
            else: return ESTADO_PROCURA_COR
        
        return ESTADO_CENTRALIZAR_COR

    def avancar_cor(self):

        self.ultimo_tempo = time.time()
        # Checa se a cor esta centralizada antes de avancar
        if cv_image is not None:
            centro, media, maior_contorno_area = visao_module.identifica_cor(cv_image, COR_MENOR_LISTA[self.indice_cor], COR_MAIOR_LISTA[self.indice_cor])

            if maior_contorno_area > 1000:

                if abs(media[0]-centro[0]) < MARGEM:

                    if self.ranges[0] > 1.5:                   
                        # Afastado da proxima parede
                        # Verificar se está mais perto de uma parede lateral
                        vel = Twist(Vector3(0.25,0,0), Vector3(0,0,0))
                        if self.ranges[270] - self.ranges[90] < -0.2:
                            vel.angular.z += 0.1
                        elif self.ranges[270] - self.ranges[90] > 0.2:
                            vel.angular.z -= 0.1

                        velocidade_saida.publish(vel)
                        return ESTADO_AVANCAR_COR
                    else:
                        # Perto da caixa - parar e trocar de cor
                        vel = Twist(Vector3(0.0,0,0), Vector3(0,0,0))
                        velocidade_saida.publish(vel)
                        rospy.sleep(2.0)
                        self.indice_cor += 1

                        if self.indice_cor >= len(COR_MENOR_LISTA):
                            return None

                        self.ultimo_tempo = time.time()
                        return ESTADO_PROCURA_COR
                
                else: return ESTADO_CENTRALIZAR_COR

            else: return ESTADO_PROCURA_COR
        
        else: ESTADO_AVANCAR_COR # Estado padrao caso nao haja imagem


    def controle(self):
        print('Estado: ', self.estado)
        if(self.estado == ESTADO_PROCURA_COR):
            self.estado = self.procura_cor()
        elif(self.estado == ESTADO_CENTRALIZAR_COR):
            self.estado = self.centraliza_cor()
        elif(self.estado == ESTADO_AVANCAR_COR):
            self.estado = self.avancar_cor()


if __name__=="__main__":
    rospy.init_node("Q3")

    topico_imagem = "/camera/image/compressed"

    recebedor = rospy.Subscriber(topico_imagem, CompressedImage, roda_todo_frame, queue_size=4, buff_size = 2**24)

    print("Usando ", topico_imagem)

    velocidade_saida = rospy.Publisher("/cmd_vel", Twist, queue_size = 1)

    try:
        vel = Twist(Vector3(0,0,0), Vector3(0,0,0))
        
        maquina_estados = Estados()
        while not rospy.is_shutdown():

            maquina_estados.controle()

            # ATENÇÃO: ao mostrar a imagem aqui, não podemos usar cv2.imshow() dentro do while principal!! 
            if cv_image is not None:
                cv2.imshow("cv_image", cv_image)
                cv2.waitKey(1)

            rospy.sleep(0.1)

    except rospy.ROSInterruptException:
        print("Ocorreu uma exceção com o rospy")

