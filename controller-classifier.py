from operator import attrgetter

from ryu.app import simple_switch_13
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
#import conf
import mysql.connector
import pandas as pd
import numpy as np
from sklearn.externals import joblib
import sys,re,time
import warnings
from sklearn import preprocessing


class SimpleMonitor13(simple_switch_13.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}

        #keep record of data when flow start to inserting
        self.is_begin = False

        self.monitor_thread = hub.spawn(self._monitor)

        #initialize connection with database
        self.mydb = mysql.connector.connect(host = "localhost", user = "root", passwd="1234", database = "sdn")
        self.mycursor = self.mydb.cursor()

        #initialize algorithm
        self.algorithm = "tree"




    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            f = open("conf.txt", "r")
            line = f.readline()
            self.algorithm = line.split('"')[1]
            print(self.algorithm)
            self._create_dataframe()
            hub.sleep(5)


    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

        req = parser.OFPMeterFeaturesStatsRequest(datapath, 0)
        datapath.send_msg(req)

        req = parser.OFPMeterStatsRequest(datapath, 0, ofproto.OFPM_ALL)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match['in_port'],
                                             flow.match['eth_dst'])):

        	#store collected flow data in mysql
            if stat.packet_count>300:
                self.is_begin=True
                sql = "INSERT into flowStats (dp_id,in_port,eth_dst,packets,bytes,duration_sec,length) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                val=(str(ev.msg.datapath.id), str(stat.match['in_port']), str(stat.match['eth_dst']),  str(stat.packet_count), str(stat.byte_count), str(stat.duration_sec),str(stat.length))
                self.mycursor.execute(sql, val)
                self.mydb.commit()

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        for stat in sorted(body, key=attrgetter('port_no')):

        	#store collected port data in mysql
            if self.is_begin and stat.port_no <=2:
                sql = "INSERT into portStats (dp_id,port_no,rx_bytes,rx_pkts,tx_bytes,tx_pkts) VALUES (%s, %s, %s, %s, %s, %s)"
                val = (str(ev.msg.datapath.id), str(stat.port_no), str(stat.rx_bytes),str(stat.rx_packets), str(stat.tx_bytes), str(stat.tx_packets))
                self.mycursor.execute(sql, val)
                self.mydb.commit()

# create dataframe in pandas and complete classfication
    def _create_dataframe(self):
    	#connected to mysql again to read the updated data
        mydb = mysql.connector.connect(host = "localhost", user = "root", passwd="1234", database = "sdn")
        mycursor = mydb.cursor()
        sql = "select * from flowStats order by id desc limit 1"
        mycursor.execute(sql)
        row_f = mycursor.fetchall()
        sql2 = "select * from portStats order by id desc limit 1"
        mycursor.execute(sql2)
        row_p= mycursor.fetchall()

        if len(row_f)>0 and len(row_p) > 0:
      
            flow = list(row_f[0])[:-1]
    
            port = list(row_p[0])[:-1]


            #if len(flow) and len(port):
            flow_df = pd.DataFrame([flow],columns=["dp_id","in_port","eth_dst","packets","bytes","duration_sec","length"])
            port_df = pd.DataFrame([port], columns=["dp_id","port_no","rx_bytes","rx_pkts","tx_bytes","tx_pkts"])
            df = pd.concat([flow_df, port_df], axis=1, join='inner')


            #The mapping relationship for semi-supervised learning
            qos_dict={"0":"3", "1":"2", "2":"1"}
            app_dict={"0":"cbc", "1":"hangout", "2":"vimeo", "3":"voip","4":"youtube"}

            if self.algorithm == "tree":
            	#data preprocessing
                feature_list = ['in_port', 'packets', 'bytes', 'duration_sec', 'port_no','rx_bytes', 'rx_pkts', 'tx_bytes','tx_pkts']
                df = df[feature_list]

                #ignore warning
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    clf_app = joblib.load('tree_app.pkl')
                    res=clf_app.predict(df)
                    print("Applying tree algorithm")
                    print("Application:")
                    print(res)
                    clf_qos =joblib.load('tree_qos.pkl')
                    res = clf_qos.predict(df)
                    print("QoS level(1 refers to the highest, 3 refers to the lowest):")
                    print(res)

            if self.algorithm == "kmeans":
            	#data preprocessing
                df["bytes"] = pd.to_numeric(df.bytes)
                df["packets"] = pd.to_numeric(df.packets)
                df["by_per_pkt"] = df["bytes"]/df["packets"]
                features = ["by_per_pkt","rx_pkts","tx_pkts"]

                #mapping function for unsupervised learning
                app_dic={0:"cbc", 1:"hangout", 2:"vimeo",3:"voip", 4:"youtube"}


                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    scaler = preprocessing.MinMaxScaler(feature_range=(0,1))
                    df[features] = scaler.fit_transform(df[features])
                    df = df[features]
                    self.logger.info("The applications are labeled with number as the 0-4, and the QoS is classify as 0-2")
                    clf_app = joblib.load('kmeans_model_app.pkl')
                    res=clf_app.predict(df)
                    print("Applying kmeans algorithm:")
                    print("Application:")
                    print(app_dic[res[0]])
                    clf_qos =joblib.load('kmeans_model_qos.pkl')
                    res = clf_qos.predict(df)
                    print("QoS level:")
                    print(res[0])

            if self.algorithm == "svm":
            	#data preprocessing
                df["bytes"] = pd.to_numeric(df.bytes)
                df["packets"] = pd.to_numeric(df.packets)
                df["by_per_pkt"] = df["bytes"]/df["packets"]
                features = ["bytes","rx_pkts","tx_pkts","packets","by_per_pkt"]


                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    scaler = preprocessing.MinMaxScaler(feature_range=(0,1))
                    df[features] = scaler.fit_transform(df[features])
                    df = df[features]
                    clf_app = joblib.load('semi_svm_app.pkl')
                    res=clf_app.predict(df)
                    print("Applying svm algorithm:")
                    print("Application:")
                    print(app_dict[str(res[0])])
                    clf_qos =joblib.load('semi_svm_qos.pkl')
                    res = clf_qos.predict(df)
                    print("QoS level(1 refers to the highest, 3 refers to the lowest):")
                    print(qos_dict[str(res[0])])

            if self.algorithm == "nb":

                #data preprocessing
                df["bytes"] = pd.to_numeric(df.bytes)
                df["packets"] = pd.to_numeric(df.packets)
                df["by_per_pkt"] = df["bytes"]/df["packets"]
                features = ["bytes","rx_pkts","tx_pkts","packets","by_per_pkt"]

                 
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    scaler = preprocessing.MinMaxScaler(feature_range=(0,1))
                    df[features] = scaler.fit_transform(df[features])
                    df = df[features]
                    clf_app = joblib.load('semi_nb_app.pkl')
                    res=clf_app.predict(df)
                    print("Applying naive bayes algorithm:")
                    print("Application:")
                    print(app_dict[str(res[0])])
                    clf_qos =joblib.load('semi_nb_qos.pkl')
                    res = clf_qos.predict(df)
                    print("QoS level(1 refers to the highest, 3 refers to the lowest):")
                    print(qos_dict[str(res[0])])









