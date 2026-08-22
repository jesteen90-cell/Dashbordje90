from transfer_optimizer_v2 import legal,optimize

def p(i,pos,team,cost,x1,x2,x3):return {'id':i,'element_type':pos,'team':team,'now_cost':cost,'_x':{1:x1,2:x2,3:x3}}

def build():
 s=[];i=1
 for pos,n in ((1,2),(2,5),(3,5),(4,3)):
  for j in range(n):s.append(p(i,pos,(i%10)+1,50 if pos!=4 else 70,3+j*.05,3+j*.05,3+j*.05));i+=1
 pool=list(s)+[p(100,3,20,50,3.1,8.0,8.0),p(101,4,19,70,7.5,3.0,3.0),p(102,2,18,50,6.5,6.5,6.5)]
 return s,pool

def main():
 s,players=build();assert legal(s)
 r=optimize(players,s,bank=0,gws=[1,2,3],weights={1:1,2:.9,3:.8},free_transfers=1,beam_width=40,per_pos=8,max_transfers_per_gw=2)
 assert len(r['moves'])==3 and r['gain']>=0
 assert all(m['action'] in ('bank','transfer') for m in r['moves'])
 assert all(1<=rft<=5 for rft in [r['free_transfers']])
 assert r['hit_points']>=0
 # Banking from one FT must permit two FTs next week in at least a bank-only toy case.
 rb=optimize(s,s,bank=0,gws=[1],weights={1:1},free_transfers=1,beam_width=5,per_pos=2,max_transfers_per_gw=0)
 assert rb['moves'][0]['action']=='bank' and rb['free_transfers']==2
 print('transfer optimizer v2.3 PASS',r['gain'],r['hit_points'],r['moves'])
if __name__=='__main__':main()
