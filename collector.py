from operator import attrgetter

from ryu.app import simple_switch_13
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub


class SimpleMonitor13(simple_switch_13.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}

        #keep record of data when flow start to inserting
        self.is_begin = False

        self.monitor_thread = hub.spawn(self._monitor)
        file = open("FlowStats.txt","w")
        file.write('dp_id,in_port,eth_dst,packets,bytes,duration_sec,target')
        file.close()

        file = open("PortStats.txt","w")
        file.write('dp_id,port_no,rx_bytes,rx_pkts,tx_bytes,tx_pkts')
        file.close()

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

        #for flow in body:
        #    if flow.priority==1:
                #print(flow)
                #print('\n')

        f1=open("FlowStats.txt", "a+")
        self.logger.info('datapath         '
                         'in-port  eth-dst           '
                         'out-port packets  bytes')
        self.logger.info('---------------- '
                         '-------- ----------------- '
                         '-------- -------- --------')
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match['in_port'],
                                             flow.match['eth_dst'])):
            self.logger.info('%016x %8x %17s %8x %8d %8d',
                            ev.msg.datapath.id,stat.match['in_port'],
                            stat.match['eth_dst'],
                            stat.instructions[0].actions[0].port,
                            stat.packet_count, stat.byte_count)
            target="vimeo"
            if stat.packet_count>300:
                self.is_begin=True
                f1.write("\n"+str(ev.msg.datapath.id) + ","+ str(stat.match['in_port'])+ "," +str(stat.match['eth_dst'])+ "," + str(stat.packet_count) + "," + str(stat.byte_count)+ "," + str(stat.duration_sec)+","+str(target))
        f1.close()

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body

        f1=open("PortStats.txt", "a+")
        self.logger.info('datapath         port     '
                         'rx-pkts  rx-bytes rx-error '
                         'tx-pkts  tx-bytes tx-error')
        self.logger.info('---------------- -------- '
                         '-------- -------- -------- '
                         '-------- -------- --------')
        for stat in sorted(body, key=attrgetter('port_no')):
            self.logger.info('%016x %8x %8d %8d %8d %8d %8d %8d',
                             ev.msg.datapath.id, stat.port_no,
                             stat.rx_packets, stat.rx_bytes, stat.rx_errors,
                             stat.tx_packets, stat.tx_bytes, stat.tx_errors)


            if self.is_begin and stat.port_no <=2:
                f1.write("\n{},{},{},{},{},{}".format(ev.msg.datapath.id, stat.port_no, stat.rx_bytes,stat.rx_packets, stat.tx_bytes, stat.tx_packets))
        f1.close()

    @set_ev_cls(ofp_event.EventOFPMeterFeaturesStatsReply, MAIN_DISPATCHER)
    def _meter_features_stats_reply_handler(self, ev):
        features = []
        body = ev.msg.body
        for stat in body:
            features.append('max_meter=%d band_types=0x%08x'
            'capabilities=0x%08x max_bands=%d '
             'max_color=%d' %
              (stat.max_meter, stat.band_types,
               stat.capabilities, stat.max_bands,
               stat.max_color))
        print('MeterFeaturesStats:', features)


    @set_ev_cls(ofp_event.EventOFPMeterStatsReply, MAIN_DISPATCHER)
    def _meter_stats_reply_handler(self, ev):
        meters =[]
        body = ev.msg.body
        for stat in body:
            meters.append('meter_id=0x%08x len=%d flow_count=%d '
            'packet_in_count=%d byte_in_count=%d '
            'duration_sec=%d duration_nsec=%d '                                             'band_stats=%s' %
            (stat.meter_id, stat.len, stat.flow_count,
            stat.packet_in_count, stat.byte_in_count,
            stat.duration_sec, stat.duration_nsec,
            stat.band_stats))
        print("Meter stats: ", meters)

