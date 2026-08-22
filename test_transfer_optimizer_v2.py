from transfer_optimizer_v2 import legal,optimize

def p(i,pos,team,cost,x1,x2,x3):return {'id':i,'element_type':pos,'team':team,'now_cost':cost,'_x':{1:x1,2:x2,3:x3}}

def build():
 s=[];i=1
 for pos,n in ((1,2),(2,5),(3,5),(4,3)):
  for j in range(n):s.append(p(i,pos,(i%10)+1,50 if pos!=4 else 70,3+j*.05,3+j*.05,3+j*.05));i+=1
 # Strong future midfielder whose GW1 gain is small: optimizer should be able to delay.
 pool=list(s)+[p(100,3,20,50,3.1,8.0,8.0),p(101,4,19,70,7.5,3.0,3.0)]
 return s,pool

def main():
 s,players=build();assert legal(s)
 r=optimize(players,s,bank=0,gws=[1,2,3],weights={1:1,2:.9,3:.8},free_transfers=1,beam_width=30,per_pos=8)
 assert len(r['moves'])==3
 assert r['gain']>=0
 assert all(m['action'] in ('bank','transfer') for m in r['moves'])
 print('transfer optimizer smoke PASS',r['gain'],r['moves'])
if __name__=='__main__':main()
